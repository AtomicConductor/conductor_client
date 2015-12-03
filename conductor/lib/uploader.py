import base64
import time
import ast
import json
import hashlib
import os
import Queue
import sys
import thread
from threading import Thread
import time
import traceback
import requests
import urllib
import collections

from conductor.setup import CONFIG, logger
from conductor.lib import api_client, common, worker

'''
This worker will pull filenames from in_queue and compute it's base64 encoded
md5, which will be added to out_queue
'''
class MD5Worker(worker.ThreadWorker):

        def __init__(self, *args, **kwargs):
            worker.ThreadWorker.__init__(self, *args, **kwargs)

        def do_work(self, job):
            logger.debug('job is %s', job)
            filename, submission_time_md5 = job
            logger.debug('checking md5 of %s', filename)
            current_md5 = common.get_base64_md5(filename)
            # if a submission time md5 was provided then check against it
            if submission_time_md5 and current_md5 != submission_time_md5:
                message = 'MD5 of %s has changed since submission\n' % filename
                message += 'submitted md5: %s\n' % submission_time_md5
                message += 'current md5:   %s' % current_md5
                logger.error(message)
                # raise message
            self.metric_store.set_dict('file_md5s', filename, current_md5)
            return (filename, current_md5)


'''
This worker will batch the computed md5's into self.batch_size chunks.
It will send a partial batch after waiting self.wait_time seconds
'''
class MD5OutputWorker(worker.ThreadWorker):
    def __init__(self, *args, **kwargs):
        worker.ThreadWorker.__init__(self, *args, **kwargs)
        self.batch_size = 20  # the controlls the batch size for http get_signed_urls
        self.wait_time = 1
        self.batch = {}

    def check_for_posion_pill(self, job):
        ''' we need to make sure we ship the last batch before we terminate '''
        if job == self.PosionPill():
            logger.debug('md5outputworker got posion pill')
            self.ship_batch()
            self.mark_done()
            thread.exit()

    # helper function to ship batch
    def ship_batch(self):
        if self.batch:
            logger.debug('sending batch: %s', self.batch)
            self.put_job(json.dumps(self.batch))
            self.batch = {}

    def target(self):

        while not common.SIGINT_EXIT:
            try:
                # block on the queue with a self.wait_time second timeout
                file_md5_tuple = self.in_queue.get(True, self.wait_time)

                self.check_for_posion_pill(file_md5_tuple)

                # add (filepath: md5) to the batch dict
                self.batch[file_md5_tuple[0]] = file_md5_tuple[1]

                # if the batch is self.batch_size, ship it
                if len(self.batch) == self.batch_size:
                    self.ship_batch()

            # This happens if no new messages are put into the queue after
            # waiting for self.wait_time seconds
            except Queue.Empty:
                self.ship_batch()
                continue
            except Exception, e:
                error_message = traceback.format_exc()
                self.error_queue.put(error_message)
                self.mark_done()

            # mark this task as done
            self.mark_done()




'''
This worker recieves a batched dict of (filename: md5) pairs and makes a
batched http api call which returns a list of (filename: signed_upload_url)
of files that need to be uploaded.

Each item in the return list is added to the out_queue.
'''
class HttpBatchWorker(worker.ThreadWorker):
    def __init__(self, *args, **kwargs):
        worker.ThreadWorker.__init__(self, *args, **kwargs)
        self.api_client = api_client.ApiClient()

    def make_request(self, job):
        response_string, response_code = self.api_client.make_request(
            uri_path='/api/files/get_upload_urls',
            verb='POST',
            headers={'Content-Type':'application/json'},
            data=job,
        )

        if response_code == 200:
            url_list = json.loads(response_string)
            return url_list
        if response_code == 204:
            return None
        else:
            raise Exception('could not make request to /api/files/get_upload_urls')

    def do_work(self, job):
        logger.debug('getting upload urls for %s', job)
        url_list = common.retry(lambda: self.make_request(job))
        return url_list

'''
This worker subscribes to a queue of (path,signed_upload_url) pairs.

For each item on the queue, it determines the size (in bytes) of the files to be
uploaded, and aggregrates the total size for all uploads.

It then places the triplet (filepath, upload_url, byte_size) onto the out_queue

The bytes_to_upload arg is used to hold the aggregrated size of all files that need
to be uploaded. Note: This is stored as an [int] in order to pass it by
reference, as it needs to be accessed and reset by the caller.
'''
class FileStatWorker(worker.ThreadWorker):
    def __init__(self, *args, **kwargs):
        worker.ThreadWorker.__init__(self, *args, **kwargs)

    def do_work(self, job):
        '''
        Job is a dict of filepath: signed_upload_url pairs.
        The FileStatWorker iterates through the dict.
        For each item, it aggregrates the filesize in bytes, and passes each
        pair as a tuple to the UploadWorker queue.
        '''

        ''' iterate through a dict of (filepath: upload_url) pairs '''
        for path, upload_url in job.iteritems():
            # logger.debug('stat: %s', path)
            byte_count = os.path.getsize(path)

            self.metric_store.increment('bytes_to_upload', byte_count)
            self.metric_store.increment('num_files_to_upload')

            self.put_job((path, upload_url))

        ''' make sure we return None, so no message is automatically added to the
        out_queue '''
        return None



'''
This woker recieves a (filepath: signed_upload_url) pair and performs an upload
of the specified file to the provided url.
'''
class UploadWorker(worker.ThreadWorker):
    def __init__(self, *args, **kwargs):
        worker.ThreadWorker.__init__(self, *args, **kwargs)
        self.chunk_size = 1048576  # 1M
        self.report_size = 10485760  # 10M
        self.api_client = api_client.ApiClient()

    def chunked_reader(self, filename):
        with open(filename, 'rb') as file:
            while worker.WORKING and not common.SIGINT_EXIT:
                data = file.read(self.chunk_size)
                if not data:
                    # we are done reading the file
                    break
                # TODO: can we wrap this in a retry?
                yield data

                # report upload progress
                self.metric_store.increment('bytes_uploaded', len(data), filename)

    def do_work(self, job):
        filename = job[0]
        upload_url = job[1]
        md5 = self.metric_store.get_dict('file_md5s', filename)
        headers = {
            'Content-MD5': md5,
            'Content-Type': 'application/octet-stream',
        }

        try:
            resp_str, resp_code = self.api_client.make_request(
                conductor_url=upload_url,
                headers=headers,
                data=self.chunked_reader(filename),
                verb='PUT')
        except Exception, e:
            error_message = 'failed to upload file %s because of:\n%s' % (filename, traceback.format_exc())
            logger.error(error_message)
            raise Exception(error_message)

        return None





class Uploader():

    sleep_time = 10

    def __init__(self, args=None):
        logger.debug("Uploader.__init__")
        self.api_client = api_client.ApiClient()
        args = args or {}
        self.location = args.get("location") or CONFIG.get("location")
        self.process_count = CONFIG['thread_count']

    def prepare_workers(self):
        logger.debug('preparing workers...')
        common.register_sigint_signal_handler()
        self.num_files_to_process = 0
        self.job_start_time = 0
        self.manager = None

    def create_manager(self, md5_only=False):
        if md5_only:
            job_description = [
                (MD5Worker, [], {'thread_count': self.process_count})
            ]
        else:
            job_description = [
                (MD5Worker, [], {'thread_count': self.process_count}),
                (MD5OutputWorker, [], {'thread_count': 1}),
                (HttpBatchWorker, [], {'thread_count': self.process_count}),
                (FileStatWorker, [], {'thread_count': 1}),
                (UploadWorker, [], {'thread_count': self.process_count}),
            ]

        manager = worker.JobManager(job_description)
        manager.start()
        return manager

    def report_status(self):
        logger.debug('started report_status thread')
        update_interval = 5
        while True:

            # don't report status if we are doing a local_upload
            if not self.upload_id:
                logger.debug('not updating status as we were not provided an upload_id')
                return

            if self.working:
                bytes_to_upload = self.manager.metric_store.get('bytes_to_upload')
                bytes_uploaded = self.manager.metric_store.get('bytes_uploaded')
                try:
                    status_dict = {
                        'upload_id': self.upload_id,
                        'size_in_bytes': bytes_to_upload,
                        'bytes_transfered': bytes_uploaded,
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
        thd = Thread(target=self.report_status)
        thd.daemon = True
        thd.start()

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

        estimated_time = (elapsed_time - elapsed_time * percent_complete) / percent_complete
        return estimated_time

    def convert_byte_count_to_string(self, byte_count, transfer_rate=False):
        apend_string = ' '

        if byte_count > 2 ** 30:
            return str(round(byte_count / float(2 ** 30), 1)) + ' GB'
        elif byte_count > 2 ** 20:
            return str(round(byte_count / float(2 ** 20), 1)) + ' MB'
        elif byte_count > 2 ** 10:
            return str(round(byte_count / float(2 ** 10), 1)) + ' KB'
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
        num_files_to_upload = self.manager.metric_store.get('num_files_to_upload')
        files_to_upload = str(num_files_to_upload)
        files_to_analyze = str(self.num_files_to_process)

        if self.job_start_time:
            elapsed_time = int(time.time()) - self.job_start_time
        else:
            elapsed_time = 0

        bytes_to_upload = self.manager.metric_store.get('bytes_to_upload')
        bytes_uploaded = self.manager.metric_store.get('bytes_uploaded')
        if bytes_to_upload:
            percent_complete = bytes_uploaded / float(bytes_to_upload)
        else:
            percent_complete = 0

        if elapsed_time:
            transfer_rate = bytes_uploaded / elapsed_time
        else:
            transfer_rate = 0


        unformatted_text = '''
################################################################################
     files to process: {files_to_analyze}
      files to upload: {files_to_upload}
       data to upload: {bytes_to_upload}
             uploaded: {bytes_uploaded}
         elapsed time: {elapsed_time}
     percent complete: {percent_complete}
        transfer rate: {transfer_rate}
       time remaining: {time_remaining}
        file progress:
'''

        bytes_to_upload = self.manager.metric_store.get('bytes_to_upload')
        bytes_uploaded = self.manager.metric_store.get('bytes_uploaded')

        formatted_text = unformatted_text.format(
            files_to_analyze=files_to_analyze,
            files_to_upload=files_to_upload,
            bytes_to_upload=self.convert_byte_count_to_string(bytes_to_upload),
            bytes_uploaded=self.convert_byte_count_to_string(bytes_uploaded),
            elapsed_time=self.convert_time_to_string(elapsed_time),
            percent_complete=str(round(percent_complete * 100, 1)) + ' %',
            transfer_rate=self.convert_byte_count_to_string(transfer_rate) + '/s',
            time_remaining=self.convert_time_to_string(
                self.estimated_time_remaining(elapsed_time, percent_complete)),
        )

        file_progress = self.manager.metric_store.get_dict('files')
        for filename in file_progress:
            formatted_text += "%s: %s\n" % (filename, file_progress[filename])

        formatted_text += "################################################################################"

        return formatted_text


    def print_status(self):
        logger.debug('starting print_status thread')
        update_interval = 3

        def sleep():
            time.sleep(update_interval)

        while True:
            if self.working:
                try:
                    logger.info(self.manager.worker_queue_status_text())
                    logger.info(self.upload_status_text())
                except Exception, e:
                    print e
                    print traceback.format_exc()
                    # pass
            sleep()

    def create_print_status_thread(self):
        logger.debug('creating console status thread')
        thd = Thread(target=self.print_status)

        # make sure threads don't stop the program from exiting
        thd.daemon = True

        # start thread
        thd.start()


    def mark_upload_finished(self, upload_id):
        finish_dict = {
            'upload_id':upload_id,
            'status': 'server_pending',
        }
        resp_str, resp_code = self.api_client.make_request(
            '/uploads/%s/finish' % upload_id,
            data=json.dumps(finish_dict),
            verb='POST')
        return True


    def mark_upload_failed(self, error_message, upload_id):
        logger.error('failing upload due to: \n%s' % error_message)

        # report error_message to the app
        resp_str, resp_code = self.api_client.make_request(
            '/uploads/%s/fail' % upload_id,
            data=error_message,
            verb='POST')

        return True

    def handle_upload_response(self, upload_files, upload_id=None, md5_only=False):
        # reset counters
        self.num_files_to_process = len(upload_files)
        self.job_start_time = int(time.time())
        self.upload_id = upload_id
        self.job_failed = False
        # signal the reporter to start working
        self.working = True

        self.prepare_workers()

        # print out info
        logger.info('upload_files contains %s files like:', len(upload_files))
        logger.info('\t%s', "\n\t".join(upload_files.keys()[:5]))

        # create worker pools
        self.manager = self.create_manager(md5_only)

        # create reporters
        logger.debug('creating report status thread...')
        self.create_report_status_thread()
        logger.info('creating console status thread...')
        self.create_print_status_thread()

        # load tasks into worker pools
        for path, md5 in upload_files.iteritems():
            self.manager.add_task((path, md5))

        # wait for work to finish
        output = self.manager.join()

        # signal to the reporter to stop working
        self.working = False
        logger.info('done uploading files')

        # report upload status
        if output:
            if upload_id:
                self.mark_upload_failed(output, upload_id)
            return output
        else:
            if upload_id:
                self.mark_upload_finished(upload_id)
            return None


    def main(self, run_one_loop=False):
        logger.info('Uploader Started. Checking for uploads...')

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
                    # TODO: consider failing if the md5's have changed since submission
                    upload_files = json_data['upload_files']
                except ValueError, e:
                    logger.error('response was not valid json: %s', resp_str)
                    time.sleep(self.sleep_time)
                    continue

                upload_id = json_data['upload_id']
                logger.info('upload_id is %s', upload_id)

                self.handle_upload_response(upload_files, upload_id)

            except Exception, e:
                logger.error('hit exception %s', e)
                logger.error(traceback.format_exc())
                time.sleep(self.sleep_time)
                continue

        logger.info('exiting uploader')


    def return_md5s(self):
        '''
        Return a dictionary of the filepaths and their md5s that were generated
        upon uploading
        '''
        return self.manager.metric_store.get_dict('file_md5s')


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
