import base64
import time
import ast
import json
import hashlib
from httplib2 import Http
import os
import Queue
import sys
from threading import Thread
import time
import traceback
import requests

from conductor.setup import CONFIG, logger
from conductor.lib import api_client, common

'''
Abstract worker class.

The class defines the basic function and data structures that all workers need.

TODO: move this into it's own lib
'''
class Worker():
    def __init__(self, in_queue, out_queue=None):
        # the in_queue provides work for us to do
        self.in_queue = in_queue

        # results of work are put into the out_queue
        self.out_queue = out_queue

    '''
    This ineeds to be implmented for each worker type. The work task from
    the in_queue is passed as the job argument.

    Returns the result to be passed to the out_queue
    '''
    def do_work(self,job):
        raise NotImplementedError

    # Basic thread target loop.
    def target(self):
        print 'on target'
        while not common.SIGINT_EXIT:
            try:
                print 'looking for work'
                # this will block until work is found
                job = self.in_queue.get(True)

                print 'got job!'
                # start working on job
                output = self.do_work(job)

                # put result in out_queue
                if output and self.out_queue:
                    self.out_queue.put(output)

                # signal that we are done with this task (needed for the
                # Queue.join() operation to work.
                self.in_queue.task_done()

            except Exception:
                # print 'hit exception: %s' % e
                print traceback.print_exc()
                print traceback.format_exc()

    '''
    Start number_of_threads threads.
    '''
    def start(self,number_of_threads=1):
        print 'in start'
        print 'number_of_threads is %s' % number_of_threads
        for i in range(number_of_threads):
            print 'starting thread %s' % i
            # thread will begin execution on self.target()
            thd = Thread(target = self.target)

            # trigger deamon mode which will cause sub-theads to exit when
            # parent thread is done
            thd.daemon = True

            # start thread
            thd.start()
            print 'done starting thread'

'''
This worker will pull filenames from in_queue and compute it's base64 encoded
md5, which will be added to out_queue
'''
class MD5Worker(Worker):
        def __init__(self, in_queue, out_queue, md5_map):
            logger.debug('starting init for MD5Worker')
            Worker.__init__(self, in_queue, out_queue)
            self.md5_map = md5_map

        # TODO: optimize blocksize
        def get_md5(self, file_path, blocksize=65536):
            logger.debug('trying to open %s', file_path)
            logger.debug('file_path.__class__ %s', file_path.__class__)

            hasher = hashlib.md5()
            afile = open(file_path, 'rb')
            buf = afile.read(blocksize)
            while len(buf) > 0:
                hasher.update(buf)
                buf = afile.read(blocksize)
            return hasher.digest()

        def get_base64_md5(self, *args, **kwargs):
            md5 = get_md5(*args)
            b64 = base64.b64encode(md5)
            logger.debug('b64 is %s', b64)
            return b64

        def do_work(self, job):
            filename = job
            md5 = get_base64_md5(filename)
            logger.debug('computed md5 %s of %s: ', md5, filename)
            self.md5_map[filename] = md5 # save filename:md5 map as we need it for uploads
            return (filename, md5)


'''
This worker will batch the computed md5's into self.batch_size chunks.
It will send a partial batch after waiting self.wait_time seconds
'''
class MD5OutputWorker(Worker):
    def __init__(self, in_queue, out_queue):
        logger.debug('starting init for MD5OutputWorker')
        Worker.__init__(self, in_queue, out_queue)
        self.batch_size = 100 # the controlls the batch size for http get_signed_urls
        self.wait_time = 5


    def target(self):
        batch={}

        # helper function to ship batch
        def ship_batch():
            if batch:
                out_queue.put(batch)
                batch = {}

        while not common.SIGINT_EXIT:
            try:
                # block on the queue with a self.wait_time second timeout
                file_md5_tuple = in_queue.get(True, self.wait_time)

                # add (filepath: md5) to the batch dict
                batch[file_md5_tuple[0]] = file_md5_tuple[1]

                # if the batch is self.batch_size, ship it
                if len(batch) == self.batch_size:
                    ship_batch()

                # mark this task as done
                in_queue.task_done()

            # This happens if no new messages are put into the queue after
            # waiting for self.wait_time seconds
            except Queue.Empty:
                ship_batch()



'''
This worker recieves a batched dict of (filename: md5) pairs and makes a
batched http api call which returns a list of (filename: signed_upload_url)
of files that need to be uploaded.

Each item in the return list is added to the out_queue.
'''
class HttpBatchWorker(Worker):
    def __init__(self, in_queue, out_queue):
        logger.debug('starting init for HttpBatchWorker')
        Worker.__init__(self, in_queue, out_queue)

    def do_work(self, job):
        # send a batch request
        response_string, response_code = self.api_client.make_request(
            uri_path = '/api/files/get_upload_urls',
            # TODO: PUT vs. POST?
            verb = 'POST',
            data = job
        )

        if response_code == 200:
            # TODO: verfify json
            url_list = json.loads(response_string)
            return url_list
        else:
            logger.error('response code was %s' % response_code)

        return None

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
class FileStatWorker(Worker):
    def __init__(self, in_queue, out_queue, bytes_to_upload):
        logger.debug('starting init for FileStatWorker')
        Worker.__init__(self, in_queue, out_queue)
        self.bytes_to_upload = bytes_to_upload

    def do_work(self, job):
        '''
        Job is a dict of filepath: signed_upload_url pairs.
        The FileStatWorker iterates through the dict.
        For each item, it aggregrates the filesize in bytes, and passes each
        pair as a tuple to the UploadWorker queue.
        '''

        ''' iterate through a dict of (filepath: upload_url) pairs '''
        for path, upload_url in job.iteritems():
            # TODO: handle non-existent paths
            byte_count = os.path.getsize(path)

            # update aggregrate bytes_to_upload count
            self.bytes_to_upload[0] += byte_count

            logging.debug('adding %s to list of files to be uploaded. Size: %s', (path, byte_count))
            self.out_queue.put((path,upload_url, byte_count))

        ''' make sure we return None, so no message is automatically added to the
        out_queue '''
        return None

    '''
    This worker can only run in a single thread due to non-locking
    data-structures.
    '''
    def start(self):
        return super(FileStatWorker, self).start(1)


'''
This woker recieves a (filepath: signed_upload_url) pair and performs an upload
of the specified file to the provided url.
'''
class UploadWorker(Worker):
    def __init__(self, in_queue, out_queue, md5_map):
        logger.debug('starting init for HttpBatchWorker')
        Worker.__init__(self, in_queue, out_queue)
        self.chunk_size = 1048576 # 1M
        self.md5_map = md5_map
        self.report_size = 10485760 # 10M

    def report_status(self, incremental = True):
        amount_of_bytes_to_report = self.bytes_read - self.bytes_reported
        if incremental:
            # only report if we've uploaded more than self.report_size
            if amount_of_bytes_to_report < self.report_size:
                return

        self.out_queue.put(amount_of_bytes_to_report)
        self.bytes_reported += amount_of_bytes_to_report

    def chunked_reader(self):
        with open(self.filename, 'rb') as file:
            while True:
                data = file.read(self.chunk_size)
                if not data:
                    # we are done reading the file
                    break
                self.bytes_read += len(data)

                # this should block until chunk is uploaded
                yield data

                # report upload progress
                self.report_status()

        # send a final report
        self.report_status(incremental=False)

    def do_work(self, job):
        self.bytes_reported = 0
        self.bytes_read = 0

        self.filename = job[0]
        self.upload_url = job[1]
        self.byte_count = job[2]

        logger.info("Uploading file: %s", self.filename)
        md5 = self.md5_map[self.filename]

        response = self.do_upload(upload_url, md5, self.filename)
        headers={
            'Content-Type': 'application/octet-stream',
            'Content-MD5': md5,
        }

        response = common.retry(lambda:  requests.put(upload_url, data=chunked_reader(), headers=headers))

        # TODO: verify upload
        # return resp, content
        logger.debug('finished uploading %s', self.filename)
        return None


'''
The UploadProgressWorker aggregrates the total amount of bytes that have been uplaoded.

It gets bytes uploaded from worker threads and sums them into the bytes_uploaded arg
'''
class UploadProgressWorker(Worker):
    def __init__(self, in_queue, out_queue, bytes_uploaded):
        logger.debug('starting init for HttpBatchWorker')
        Worker.__init__(self, in_queue, out_queue)
        self.bytes_uploaded = bytes_uploaded

    def do_work(self, job):
        self.bytes_uploaded[0] += job
        return None

    '''
    This worker can only run in a single thread due to non-locking
    data-structures.
    '''
    def start(self):
        return super(FileStatWorker, self).start(1)


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
        self.bytes_to_upload = [0] # hack for passing an int by reference
        self.bytes_uploaded = [0] # hack for passing an int by reference
        self.md5_map = {}
        self.worker_pools = []
        self.create_worker_pools()
        self.working = False
        self.create_report_status_thread()

    def get_upload_url(self, filename):
        uri_path = '/api/files/get_upload_url'
        # TODO: need to pass md5 and filename
        md5 = self.get_base64_md5(filename)
        params = {
            'filename': filename,
            'md5': md5
        }
        logger.debug('params are %s', params)
        response_string, response_code = self.api_client.make_request(uri_path=uri_path, params=params)
        # TODO: validate that no error occured via error code
        return response_string, response_code, md5

    def load_md5_process_queue(self, md5_process_queue, file_list):
        '''
        Add all items in the file_list to the md5_process_queue so workers can
        work off the queue
        '''
        for upload_file in file_list:
            logger.debug('adding %s to queue', upload_file)
            md5_process_queue.put(upload_file)

    def wait_for_workers(self):
        logger.info('waiting for workers to finish...')
        for index, worker_pool in enumerate(self.worker_queues):
            logger.debug('waiting for worker %s: %s', (index,worker_pool))
            worker_pool.join()

    def create_worker_pools(self)
        # create input and output for the md5 workers
        md5_process_queue = queue.Queue()
        md5_output_queue = queue.Queue()
        http_batch_queue = queue.Queue()
        file_stat_queue = queue.Queue()
        upload_queue = queue.Queue()
        upload_progress_queue = queue.Queue()

        # ordered list of worker queues. this needs to be in pipeline order for
        # wait_for_workers() to function correctly
        self.worker_queues = [
            md5_process_queue,
            md5_output_queue,
            http_batch_queue,
            file_stat_queue,
            upload_queue,
            upload_progress_queue,
        ]


        # Let's make the worker queues avilable as a dict and let's see what
        # happens
        self.worker_queue_dict = {}

        # create md5 worker pool threads
        md5_worker = MD5Worker(md5_process_queue, md5_output_queue)
        md5_worker.start(self.process_count/4)

        # create md5 output worker
        md5_output_worker = MD5OutputWorker(md5_output_worker,http_batch_queue, self.md5_map)
        md5_output_worker.start()

        # creat http batch worker
        http_batch_worker = HttpBatchWorker(httpbatchworker, file_stat_queue)
        http_batch_worker.start(self.process_count/4)

        # create filestat worker
        file_stat_worker = Filestatworker(file_stat_queue, upload_queue, self.bytes_to_upload)
        file_stat_worker.start() # forced to a single thread

        # create upload workers
        upload_worker = UploadWorker(upload_queue, upload_progress_queue, self.md5_map)
        upload_worker.start(self.process_count)

        # create upload progress worker
        upload_worker = UploadProgressWorker(upload_queue, upload_progress_queue, self.bytes_uploaded)
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

        def sleep()
            time.sleep(update_interval)

        while True:
            if not self.working:
                sleep
                continue
            try:
                status_dict = {
                    'upload_id':upload_id,
                    'size_in_bytes': self.bytes_to_upload,
                    'bytes_transfered': self.bytes_uploaded,
                }
                resp_str, resp_code = self.api_client.make_request(
                    '/uploads/%s/update' % upload_id,
                    data=json.dumps(finish_dict),
                    verb='POST')

            except:
                pass

            sleep


    def create_report_status_thread(self):
        print 'creating reporter thread'
        # thread will begin execution on self.target()
        thd = Thread(target = self.report_status)

        # start thread
        thd.start()
        print 'done starting reporter thread'


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
                logger.debug('recieved next upload from app: %s\n\t%s', resp_code, resp_str)

                try:
                    json_data = json.loads(resp_str)
                    logger.debug('json_data is: %s', json_data)
                    upload_files = json_data['upload_files'].split(',')
                    logger.debug('upload_files is: %s', upload_files)
                except ValueError, e:
                    logger.error('response was not valid json: %s', resp_str)
                    time.sleep(self.sleep_time)
                    continue

                upload_id = json_data['upload_id']
                logger.info('uploading files for upload task %s: \n\t%s', upload_id, "\n\t".join(upload_files))

                # reset bytes_to_upload counter
                self.bytes_to_upload = [0]

                # reset md5_map
                self.md5_map = {}

                # signal the reporter to start working
                self.working = True

                # load upload_file list to begin processing
                self.load_md5_process_queue(self, self.md5_process_queue, upload_files):

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

            except Exception, e:
                logger.error('hit exception %s', e)
                logger.error(traceback.format_exc())
                time.sleep(self.sleep_time)
                continue

    # wait for work to finish
    self.wait_for_workers()

    logger.info('exiting uploader')

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
