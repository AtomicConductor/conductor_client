import base64
import time
import ast
import json
import hashlib
from httplib2 import Http
import os
import Queue
import sys
import thread
from threading import Thread
import time
import traceback
import requests
import urllib

from conductor.setup import CONFIG, logger
from conductor.lib import api_client, common, worker

'''
This worker will pull filenames from in_queue and compute it's base64 encoded
md5, which will be added to out_queue
'''
class MD5Worker(worker.ThreadWorker):
        def __init__(self, in_queue, out_queue, error_queue, md5_map):
            # logger.debug('starting init for MD5Worker')
            worker.ThreadWorker.__init__(self, in_queue, out_queue, error_queue)
            self.md5_map = md5_map

        # TODO: optimize blocksize
        def get_md5(self, file_path, blocksize=65536):
            # logger.debug('trying to open %s', file_path)
            # logger.debug('file_path.__class__ %s', file_path.__class__)

            hasher = hashlib.md5()
            afile = open(file_path, 'rb')
            buf = afile.read(blocksize)
            while len(buf) > 0:
                hasher.update(buf)
                buf = afile.read(blocksize)
            return hasher.digest()

        def get_base64_md5(self, *args, **kwargs):
            md5 = self.get_md5(*args)
            b64 = base64.b64encode(md5)
            # logger.debug('b64 is %s', b64)
            return b64

        def do_work(self, job):
            filename = job
            md5 = self.get_base64_md5(filename)
            # logger.debug('computed md5 %s of %s: ', md5, filename)
            self.md5_map[filename] = md5 # save filename:md5 map as we need it for uploads
            return (filename, md5)


'''
This worker will batch the computed md5's into self.batch_size chunks.
It will send a partial batch after waiting self.wait_time seconds
'''
class MD5OutputWorker(worker.ThreadWorker):
    def __init__(self, in_queue, out_queue, error_queue):
        # logger.debug('starting init for MD5OutputWorker')
        worker.ThreadWorker.__init__(self, in_queue, out_queue)
        self.batch_size = 20 # the controlls the batch size for http get_signed_urls
        self.wait_time = 5
        self.batch={}
        self.error_queue = error_queue

    def target(self):

        # helper function to ship batch
        def ship_batch():
            if self.batch:
                self.put_job(json.dumps(self.batch))
                self.batch = {}

        while worker.WORKING and not common.SIGINT_EXIT:
            try:
                # block on the queue with a self.wait_time second timeout
                file_md5_tuple = self.in_queue.get(True, self.wait_time)

                # add (filepath: md5) to the batch dict
                self.batch[file_md5_tuple[0]] = file_md5_tuple[1]

                # if the batch is self.batch_size, ship it
                if len(self.batch) == self.batch_size:
                    ship_batch()

                # mark this task as done
                self.in_queue.task_done()

            # This happens if no new messages are put into the queue after
            # waiting for self.wait_time seconds
            except Queue.Empty:
                ship_batch()
            except Exception, e:
                self.error_queue.put(e)



'''
This worker recieves a batched dict of (filename: md5) pairs and makes a
batched http api call which returns a list of (filename: signed_upload_url)
of files that need to be uploaded.

Each item in the return list is added to the out_queue.
'''
class HttpBatchWorker(worker.ThreadWorker):
    def __init__(self, in_queue, out_queue, error_queue):
        # logger.debug('starting init for HttpBatchWorker')
        worker.ThreadWorker.__init__(self, in_queue, out_queue, error_queue)
        self.api_client = api_client.ApiClient()

    def make_request(self, job):
        response_string, response_code = self.api_client.make_request(
            uri_path = '/api/files/get_upload_urls',
            # TODO: PUT vs. POST?
            verb = 'POST',
            headers = {'Content-Type':'application/json'},
            data = job,
        )

        if response_code == 200:
            # TODO: verfify json
            url_list = json.loads(response_string)
            return url_list
        if response_code == 204:
            pass
            # logger.info('file already uptodate')
        else:
            # TODO: make this raise so retry works properly
            logger.error('response_string was %s' % response_string)
            logger.error('response code was %s' % response_code)
            os._exit(1)

    def do_work(self, job):
        # send a batch request

        try:
            url_list = common.retry(lambda: self.make_request(job))
        except Exception, e:
            pass

        return url_list

'''
This worker subscribes to a queue of (path,signed_upload_url) pairs.

For each item on the queue, it determines the size (in bytes) of the files to be
uploaded, and aggregrates the total size for all uploads.

It then places the triplet (filepath, upload_url, byte_size) onto the out_queue

The bytes_to_upload arg is used to hold the aggregrated size of all files that need
to be uploaded. Note: This is stored as an [int] in order to pass it by
reference, as it needs to be accessed and reset by the caller.

This worker can only be run in a single thread
'''
class FileStatWorker(worker.ThreadWorker):
    def __init__(self, in_queue, out_queue, error_queue, bytes_to_upload, num_files_to_upload):
        # logger.debug('starting init for FileStatWorker')
        worker.ThreadWorker.__init__(self, in_queue, out_queue, error_queue)
        self.bytes_to_upload = bytes_to_upload
        self.num_files_to_upload = num_files_to_upload

    def do_work(self, job):
        '''
        Job is a dict of filepath: signed_upload_url pairs.
        The FileStatWorker iterates through the dict.
        For each item, it aggregrates the filesize in bytes, and passes each
        pair as a tuple to the UploadWorker queue.
        '''

        ''' iterate through a dict of (filepath: upload_url) pairs '''
        for path, upload_url in job.iteritems():

            # logger.debug('need to upload: %s', path)
            # TODO: handle non-existent paths
            byte_count = os.path.getsize(path)

            # update aggregrate bytes_to_upload count and num_files_to_upload
            # logger.debug('adding %s to self.bytes_to_upload[0]', byte_count)
            # logger.debug('self.bytes_to_upload[0] is %s', self.bytes_to_upload[0])
            self.bytes_to_upload[0] += byte_count
            self.num_files_to_upload[0] += 1
            # logger.debug('self.num_files_to_upload is %s', self.num_files_to_upload)

            # logger.debug('adding %s to list of files to be uploaded. Size: %s', path, byte_count)
            self.put_job((path,upload_url, byte_count))

        ''' make sure we return None, so no message is automatically added to the
        out_queue '''
        return None

    '''
    This worker can only run in a single thread due to non-locking
    data-structures.
    '''
    def start(self):
        return worker.ThreadWorker.start(self, 1)


'''
This woker recieves a (filepath: signed_upload_url) pair and performs an upload
of the specified file to the provided url.
'''
class UploadWorker(worker.ThreadWorker):
    def __init__(self, in_queue, out_queue, error_queue, md5_map):
        # logger.debug('starting init for HttpBatchWorker')
        worker.ThreadWorker.__init__(self, in_queue, out_queue, error_queue)
        self.chunk_size = 1048576 # 1M
        self.md5_map = md5_map
        self.report_size = 10485760 # 10M

    def report_status(self, incremental = True):
        amount_of_bytes_to_report = self.bytes_read - self.bytes_reported
        if incremental:
            # only report if we've uploaded more than self.report_size
            if amount_of_bytes_to_report < self.report_size:
                return

        self.put_job(amount_of_bytes_to_report)
        self.bytes_reported += amount_of_bytes_to_report

    def chunked_reader(self, filename):
        with open(filename, 'rb') as file:
            while worker.WORKING and not common.SIGINT_EXIT:
                data = file.read(self.chunk_size)
                if not data:
                    # we are done reading the file
                    break
                self.bytes_read += len(data)

                # this should block until chunk is uploaded
                # TODO: can we wrap this in a retry?
                try:
                    yield data
                except Exception, e:
                    logger.error('hit error')
                    logger.error(traceback.print_exc())
                    logger.error(traceback.format_exc())
                    # TODO:
                    exit(1)

                # report upload progress
                self.report_status()

        # send a final report
        self.report_status(incremental=False)

    def do_work(self, job):
        self.bytes_reported = 0
        self.bytes_read = 0

        filename = job[0]
        upload_url = job[1]
        self.byte_count = job[2]

        # logger.info("Uploading file: %s to: %s", filename, upload_url)
        md5 = self.md5_map[filename]
        # logger.info("md5 of %s is %s", filename, md5)
        # logger.info("Again: Uploading file: %s to: %s", filename, upload_url)

        headers={
            'Content-MD5': md5,
            'Content-Type': 'application/octet-stream',
        }

        # logger.debug('%$%$%$%$%$%$%$ file deets:')
        # logger.debug('headers are %s', headers)
        # logger.debug('md5 is %s', md5)
        # logger.debug('upload_url is %s', upload_url)
        # logger.debug('filename is %s', filename)


        try:
            # logger.info('trying to upload %s to %s', filename, upload_url)
            # response = requests.put(upload_url, data=self.chunked_reader(), headers=headers)
            response = common.retry(lambda: requests.put(
                upload_url,
                data=self.chunked_reader(filename),
                headers=headers))

            if response.status_code != 200:
                logger.error('could not upload %s', filename )
                logger.error('url: %s', upload_url)
                logger.error('response.status_code is %s', response.status_code)
                logger.error('response.text is %s', response.text)
                os._exit(1)

        except Exception, e:
            logger.error('hit error')
            logger.error(traceback.print_exc())
            logger.error(traceback.format_exc())
            # TODO:
            exit(1)


        # TODO: verify upload
        # return resp, content
        # logger.debug('finished uploading %s', self.filename)
        return None


'''
The UploadProgressWorker aggregrates the total amount of bytes that have been uplaoded.

It gets bytes uploaded from worker threads and sums them into the bytes_uploaded arg
'''
class UploadProgressWorker(worker.ThreadWorker):
    def __init__(self, in_queue, out_queue, error_queue, bytes_uploaded):
        # logger.debug('starting init for HttpBatchWorker')
        worker.ThreadWorker.__init__(self, in_queue, out_queue, error_queue)
        self.bytes_uploaded = bytes_uploaded

    def do_work(self, job):
        self.bytes_uploaded[0] += job
        return None

    '''
    This worker can only run in a single thread due to non-locking
    data-structures.
    '''
    def start(self):
        return worker.ThreadWorker.start(self, 1)


class Uploader():

    sleep_time = 10

    def __init__(self, args=None):
        logger.debug("Uploader.__init__")
        self.api_client = api_client.ApiClient()
        args = args or {}
        self.location = args.get("location") or CONFIG.get("location")
        self.process_count = CONFIG['thread_count']
        common.register_sigint_signal_handler()
        logger.info('creating worker pools...')
        self.num_files_to_process = 0
        self.num_files_to_upload = [0] # hack for passing an int by reference
        self.bytes_to_upload = [0] # hack for passing an int by reference
        self.bytes_uploaded = [0] # hack for passing an int by reference
        self.md5_map = {}
        self.worker_pools = []
        self.create_worker_pools()
        self.start_error_handler()
        self.working = False
        # self.working = True
        self.job_start_time = 0
        self.create_report_status_thread()
        self.create_print_status_thread()

    def get_upload_url(self, filename, md5_hash):
        uri_path = '/api/files/get_upload_url'
        # TODO: need to pass md5 and filename
        md5 = self.get_base64_md5(filename)
        params = {
            'filename': filename,
            'md5': md5
        }
        logger.debug('params are %s', params)
        # retries?
        response_string, response_code = self.api_client.make_request(uri_path=uri_path, params=params)
        # TODO: validate that no error occured via error code
        return response_string, response_code, md5

    def load_md5_process_queue(self, md5_process_queue, file_list):
        '''
        Add all items in the file_list to the md5_process_queue so workers can
        work off the queue
        '''
        logger.info('loading %s files to be processed', len(file_list))
        for upload_file in file_list:
            # logger.debug('adding %s to queue first queue', upload_file)
            md5_process_queue.put(upload_file)

    def wait_for_workers(self):
        logger.info('waiting for workers to finish...')
        for index, worker_pool in enumerate(self.worker_queues):
            logger.debug('waiting for worker %s: %s' % (index, worker_pool))
            worker_pool.join()

    def create_worker_pools(self):
        # create input and output for the md5 workers
        error_queue = Queue.Queue()
        self.error_queue = error_queue
        md5_process_queue = Queue.Queue()
        md5_output_queue = Queue.Queue()
        http_batch_queue = Queue.Queue()
        file_stat_queue = Queue.Queue()
        upload_queue = Queue.Queue()
        upload_progress_queue = Queue.Queue()

        # ordered list of worker queues. this needs to be in pipeline order for
        # wait_for_workers() to function correctly
        self.worker_queues = [
            md5_process_queue,
            md5_output_queue,
            http_batch_queue,
            file_stat_queue,
            upload_queue,
            upload_progress_queue,
            error_queue,
        ]


        # Let's make the worker queues avilable as a dict and let's see what
        # happens
        self.worker_queue_dict = {}

        # create md5 worker pool threads
        md5_worker = MD5Worker(md5_process_queue, md5_output_queue, error_queue, self.md5_map)
        md5_worker.start()

        # create md5 output worker
        md5_output_worker = MD5OutputWorker(md5_output_queue,http_batch_queue, error_queue)
        md5_output_worker.start()

        # creat http batch worker
        http_batch_worker = HttpBatchWorker(http_batch_queue, file_stat_queue, error_queue)
        # http_batch_worker.start(self.process_count/4)
        http_batch_worker.start(self.process_count)

        # create filestat worker
        file_stat_worker = FileStatWorker(file_stat_queue,
                                          upload_queue,
                                          error_queue,
                                          self.bytes_to_upload,
                                          self.num_files_to_upload)
        file_stat_worker.start() # forced to a single thread

        # create upload workers
        upload_worker = UploadWorker(upload_queue, upload_progress_queue, error_queue, self.md5_map)
        upload_worker.start(self.process_count)

        # create upload progress worker
        upload_progress_worker = UploadProgressWorker(upload_progress_queue,
                                             None,
                                             error_queue,
                                             self.bytes_uploaded)
        upload_worker.start() # forced to a single thread

        logger.debug('done creating worker pools')

        return [
            md5_process_queue,
            md5_output_queue,
            http_batch_queue,
            file_stat_queue,
            upload_queue,
            upload_progress_queue,
        ]

    def report_status(self):
        update_interval = 20

        while True:
            if self.working:
                try:
                    status_dict = {
                        'upload_id': self.upload_id,
                        'size_in_bytes': self.bytes_to_upload[0],
                        'bytes_transfered': self.bytes_uploaded[0],
                    }

                    logger.debug('reporting status as: %s', status_dict)
                    resp_str, resp_code = self.api_client.make_request(
                        '/uploads/%s/update' % self.upload_id,
                        data=json.dumps(status_dict),
                        verb='POST')

                except Exception, e:
                    logger.error('could not report status:')
                    logger.error(traceback.print_exc())
                    logger.error(traceback.format_exc())

            time.sleep(update_interval)


    def create_report_status_thread(self):
        logger.debug('creating reporter thread')
        # thread will begin execution on self.target()
        thd = Thread(target = self.report_status)

        # make sure threads don't stop the program from exiting
        thd.daemon = True

        # start thread
        thd.start()


    def drain_queues(self):
        # http://stackoverflow.com/questions/6517953/clear-all-items-from-the-queue
        for queue in self.worker_queues:
            queue.queue.clear()

        return True

    def fail_upload(self, error):
        self.working = False
        worker.WORKING = False

        # drain work from queues
        self.drain_queues()

        # grab the stacktrace
        # it sucks to do this but it's the only/easiest way that I found to get the traceback
        try:
            raise error
        except:
            error_message = traceback.print_exc()
            error_message += traceback.format_exc()

        # report error_message to the app
        logger.debug('failing upload due to:\n%s', error_message)
        resp_str, resp_code = self.api_client.make_request(
            '/uploads/%s/fail' % self.upload_id,
            data=error_message,
            verb='POST')

        return True

    def error_handler_target(self):
        while True:
            error = self.error_queue.get(True)
            self.fail_upload(error)

    def start_error_handler(self):
        logger.debug('creating error handler thread')
        thd = Thread(target = self.error_handler_target)

        # make sure threads don't stop the program from exiting
        thd.daemon = True

        # start thread
        thd.start()

        return None

    def estimated_time_remaining(self, elapsed_time, percent_complete):
        '''
        This method estimates the time that is remaining, given the elapsed time
        and percent complete.

        It uses the following formula:

        let;
          t0 = elapsed time
          P = percent complete (0 <= n <= 1)

        time_remaining = (t0 - t0 * P) / P

        which is derived from percent_complete = elapsed_time / (elapsed_time + time_remaining)
        '''
        if not percent_complete:
            return -1

        estimated_time = ( elapsed_time - elapsed_time * percent_complete ) / percent_complete

        # logger.debug('elapsed_time is %s', elapsed_time)
        # logger.debug('percent_complete is %s', percent_complete)
        # logger.debug('estimated_time is %s', estimated_time)

        return estimated_time

    def worker_queue_status_text(self):
        queue_list = [
            'md5_process_queue',
            'md5_output_queue',
            'http_batch_queue',
            'file_stat_queue',
            'upload_queue',
            'upload_progress_queue',
            'error_queue',
        ]

        msg = '####################################\n'
        for i, queue_name in enumerate(queue_list):
            q_size = self.worker_queues[i].qsize()
            msg += '%s \titems in queue: %s\n' % (q_size, queue_name)

        return msg


    def convert_byte_count_to_string(self,byte_count,transfer_rate=False):
        apend_string = ' '

        if byte_count > 2**30:
            return str(round(byte_count / float(2**30), 1)) + ' GB'
        elif byte_count > 2**20:
            return str(round(byte_count / float(2**20), 1)) + ' MB'
        elif byte_count > 2**10:
            return str(round(byte_count / float(2**10), 1)) + ' KB'
        else:
            return str(byte_count) + ' B'


    def convert_time_to_string(self, time_remaining):
        if time_remaining > 3600:
            return str(round(time_remaining / float(3600) , 1)) + ' hours'
        elif time_remaining > 60:
            return str(round(time_remaining / float(60) , 1)) + ' minutes'
        else:
            return str(round(time_remaining, 1)) + ' seconds'


    def upload_status_text(self):
        # logger.debug('self.bytes_to_upload is %s' % self.bytes_to_upload)
        # logger.debug('self.num_files_to_upload is %s' % self.num_files_to_upload)
        files_to_analyze = "{:,}".format(self.num_files_to_process)
        files_to_upload = "{:,}".format(self.num_files_to_upload[0])

        if self.job_start_time:
            elapsed_time = int(time.time()) - self.job_start_time
        else:
            elapsed_time = 0

        if self.bytes_to_upload[0]:
            percent_complete = self.bytes_uploaded[0] / float(self.bytes_to_upload[0])
        else:
            percent_complete = 0

        if elapsed_time:
            transfer_rate = self.bytes_uploaded[0] / elapsed_time
        else:
            transfer_rate = 0


        unformatted_text = '''
####################################
     files to process: {files_to_analyze}
      files to upload: {files_to_upload}
       data to upload: {bytes_to_upload}
             uploaded: {bytes_uploaded}
         elapsed time: {elapsed_time}
     percent complete: {percent_complete}
        transfer rate: {transfer_rate}
       time remaining: {time_remaining}
####################################
'''

        formatted_text = unformatted_text.format(
            files_to_analyze=files_to_analyze,
            files_to_upload=files_to_upload,
            bytes_to_upload=self.convert_byte_count_to_string(self.bytes_to_upload[0]),
            bytes_uploaded=self.convert_byte_count_to_string(self.bytes_uploaded[0]),
            elapsed_time=self.convert_time_to_string(elapsed_time),
            percent_complete=str(round(percent_complete * 100, 1)) + ' %',
            transfer_rate=self.convert_byte_count_to_string(transfer_rate) + '/s',
            time_remaining = self.convert_time_to_string(
                self.estimated_time_remaining(elapsed_time, percent_complete)),
        )

        return formatted_text


    def print_status(self):
        update_interval = 3

        def sleep():
            time.sleep(update_interval)

        while True:
            if self.working:
                logger.info(self.worker_queue_status_text())
                logger.info(self.upload_status_text())


            sleep()

    def create_print_status_thread(self):
        logger.debug('creating console status thread')
        thd = Thread(target = self.print_status)

        # make sure threads don't stop the program from exiting
        thd.daemon = True

        # start thread
        thd.start()


    def handle_upload_response(self, upload_files, upload_id):
        # reset counters
        self.bytes_to_upload[0] = 0
        self.bytes_uploaded[0] = 0
        self.num_files_to_upload[0] = 0
        self.num_files_to_process = len(upload_files)
        self.job_start_time = int(time.time())
        self.upload_id = upload_id
        worker.WORKING = True

        # reset md5_map
        self.md5_map = {}

        # signal the reporter to start working
        self.working = True

        # load upload_file list to begin processing
        self.load_md5_process_queue(self.worker_queues[0], upload_files)

        # wait for work to finish
        self.wait_for_workers()

        # signal to the reporter to stop working
        self.working = False

        logger.info('done uploading files')
        finish_dict = {
            'upload_id':upload_id,
            'status': 'server_pending',
        }

        resp_str, resp_code = self.api_client.make_request('/uploads/%s/finish' % upload_id,
                                                           data=json.dumps(finish_dict),
                                                           verb='POST')

        return


    def main(self):
        logger.info('Starting Uploader...')

        while not common.SIGINT_EXIT:
            try:
                # TODO: we should pass args as url params, not http data
                data = {}
                data['location'] = self.location
                logger.debug("Data: %s", data)
                resp_str, resp_code = self.api_client.make_request('/uploads/client/next',
                                                                   data=json.dumps(data),
                                                                   verb='PUT')
                if resp_code == 204:
                    logger.debug('no files to upload')
                    sys.stdout.write('.')
                    sys.stdout.flush()
                    time.sleep(self.sleep_time)
                    continue
                elif resp_code != 201:
                    logger.error('recieved invalid response code from app %s', resp_code)
                    logger.error('response is %s', resp_str)
                    time.sleep(self.sleep_time)
                    continue

                print ''  # to make a newline after the 204 loop
                # logger.debug('recieved next upload from app: %s\n\t%s', resp_code, resp_str)

                try:
                    json_data = json.loads(resp_str)
                    # logger.debug('json_data is: %s', json_data)
                    upload_files = json_data['upload_files'].split(',')
                except ValueError, e:
                    logger.error('response was not valid json: %s', resp_str)
                    time.sleep(self.sleep_time)
                    continue

                upload_id = json_data['upload_id']
                logger.info('upload_id is %s', upload_id)
                logger.info('upload_files contains %s files like:', len(upload_files))
                logger.info('\t%s', "\n\t".join(upload_files[:5]))

                self.handle_upload_response(upload_files, upload_id)

            except Exception, e:
                logger.error('hit exception %s', e)
                logger.error(traceback.format_exc())
                time.sleep(self.sleep_time)
                continue

        # wait for work to finish
        self.wait_for_workers()

def run_uploader(args):
    '''
    Start the uploader process. This process will run indefinitely, polling
    the Conductor cloud app for files that need to be uploaded.
    '''
    # convert the Namespace object to a dictionary
    args_dict = vars(args)
    logger.debug('Uploader parsed_args is %s', args_dict)
    uploader = Uploader(args_dict)
    uploader.main()
