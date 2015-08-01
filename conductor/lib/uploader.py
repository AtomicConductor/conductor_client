import base64
import time
import ast
import json
import hashlib
from httplib2 import Http
import multiprocessing
import Queue as queue_exception
import sys
import threading
import time
import traceback
import requests

from conductor.setup import CONFIG, logger
from conductor.lib import api_client, common

class Uploader():

    sleep_time = 10

    def __init__(self, args=None):
        logger.debug("Uploader.__init__")
        self.api_client = api_client.ApiClient()
        args = args or {}
        self.location = args.get("location") or CONFIG.get("location")
        self.process_count = CONFIG['thread_count']
        self.batch_size # the controlls the batch size for http get_signed_urls
        common.register_sigint_signal_handler()

    def get_upload_url(self, filename, md5_hash):
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
        md5 = self.get_md5(*args)
        b64 = base64.b64encode(md5)
        logger.debug('b64 is %s', b64)
        return b64



    def load_md5_process_queue(self, md5_process_queue, file_list):
        '''
        Add all items in the file_list to the md5_process_queue so workers can
        work off the queue
        '''
        for upload_file in file_list:
            logger.debug('adding %s to queue', upload_file)
            md5_process_queue.put(upload_file)


    def md5_processor_target(self, md5_process_queue, md5_output_queue):
        '''
        Process MD5 of filenames in md5_process_queue and put a (filename,md5)
        tuple in the md5_output_queue
        '''
        while True:
            filename = md5_process_queue.get()
            md5 = self.get_base64_md5(filename)
            logger.debug('computed md5 %s of %s: ', md5, filename)
            md5_output_queue.put((filename, md5))
            # mark this task as done
            md5_process_queue.task_done()

    def create_md5_worker_pool(self, md5_process_queue, md5_output_queue):
        for i in range(self.process_count):
            thread = Thread(target=md5_processor_target, args=(md5_process_queue, md5_output_queue))
            thread.daemon = True
            thread.start


    def md5_output_queue_worker(self, md5_output_queue, http_batch_queue, md5_process_queue):
        '''
        Pull self.batch_size items off the md5_output_queue and add chunk to http_batch_queue

        Makes really sure to make sure that all work is processed by joining with the two previous work queues.
        Makes sure to ship the remaining items after previous workers have completed
        '''
        batch={}

        def work_left():
            ''' returns true if current or previous work queues have items'''
            if not md5_process_queue.empty():
                return True
            if not md5_output_queue.empty():
                return True
            return False

        def ship_batch():
            if batch:
                http_batch_queue.put(batch)
                batch = {}

        while True:
            try:
                # block on the queue with a 1 second timeout
                file_md5_tuple = md5_output_queue.get(True, 1)
                batch[file_md5_tuple[0]] = file_md5_tuple[1]
                if len(batch) == self.batch_size:
                    ship_batch()
                # mark this task as done
                md5_output_queue.task_done()
            except queue_exception.Empty:
                '''
                We have hit a timeout. This most likely means that all previous
                workers have completed, but we need to make really sure that we
                don't miss any late threads that are working on large files
                '''

                if work_left():
                    continue

                md5_process_queue.join()
                md5_output_queue.join()

                ''' check if any items have been created since we joined '''
                if work_left():
                    continue

                ''' send off the remaining batch '''
                ship_batch()

                ''' we're done! '''
                return

    def create_md5_batch_worker(self,md5_output_queue, http_batch_queue, md5_process_queue):
        thread = Thread(target=md5_output_queue_worker, args=(md5_output_queue, http_batch_queue, md5_process_queue))
        thread.daemon = True
        thread.start

    def http_worker_pool_target(self, http_batch_queue, signed_upload_url_queue):
        while True:
            http_batch = http_batch_queue.get()

            # send a batch request
            response_string, response_code = self.api_client.make_request(
                uri_path = '/api/files/get_upload_urls',
                # TODO: PUT vs. POST?
                verb = 'POST',
                data = http_batch
            )

            if response_code == 200:
                # TODO: verfify json
                url_list = json.loads(response_string)
                for path, upload_url in url_list.iteritems():
                    signed_upload_url_queue.put((path,upload_url))
                http_batch_queue.task_done()
            else:
                logger.error('response code was %s' % response_code)
                    http_batch_queue.put(http_batch)



    def create_http_request_pool(self, http_batch_queue, signed_upload_url_queue):
        for i in range(self.process_count):
            thread = Thread(target=http_worker_pool_target, args=(http_batch_queue, signed_upload_url_queue))
            thread.daemon = True
            thread.start


    def create_upload_worker_target(self, signed_upload_url_queue, finished_queue):
        while True:
            signed_upload_url_item = signed_upload_url_queue.get()
            filename = signed_upload_url_item[0]
            upload_url = signed_upload_url_item[1]

            logger.info("Uploading file: %s", filename)
            response = self.do_upload(upload_url, "PUT", md5, filename)
            logger.debug('finished uploading %s', filename)


            signed_upload_url_queue.task_done()

    def create_upload_worker_pool(self, signed_upload_url_queue, finished_queue):
        for i in range(self.process_count):
            thread = Thread(target=create_upload_worker_target, args=(signed_upload_url_queue, finished_queue))
            thread.daemon = True
            thread.start



    def run_uploads(self, file_list):
        if not file_list:
            logger.debug("No files to upload. Skipping run_uploads")
            return


        # create input and output for the md5 workers
        md5_process_queue = multiprocessing.Queue()
        md5_output_queue = multiprocessing.Queue()

        # load the input queue. this must happen before we create the workers
        self.load_md5_process_queue(md5_process_queue,file_list)

        # create md5 worker pool threads
        self.create_md5_worker_pool(md5_process_queue, md5_output_queue)


        # batch (filename,md5) tuples for http requests
        http_batch_queue = multiprocessing.Queue()
        self.create_md5_batch_worker(md5_output_queue, http_batch_queue, md5_process_queue)


        # create http client worker pool
        signed_upload_url_queue = multiprocessing.Queue()
        self.create_http_request_pool(http_batch_queue,signed_upload_url_queue)


        # create upload_worker pool
        finished_queue = multiprocessing.Queue()
        self.create_upload_worker_pool(signed_upload_url_queue, finished_queue)

        # wait
        md5_process_queue.join()
        md5_output_queue.join()
        http_batch_queue.join()
        signed_upload_url_queue.join()

        logger.info('done')
        return

        # kill rest

        upload_queue = multiprocessing.Queue()
        for upload_file in file_dict:
            logger.debug('adding %s:%s to queue' % (upload_file, file_dict[upload_file]))
            upload_queue.put((upload_file, file_dict[upload_file]))

        threads = []
        for n in range(self.process_count):

            thread = threading.Thread(target=self.upload_file, args=(upload_queue,))

            thread.start()
            threads.append(thread)

        for idx, thread in enumerate(threads):
            logger.debug('waiting for thread: %s', idx)
            thread.join()
        logger.debug('done with threading stuff')



    def upload_file(self, upload_queue):
        logger.debug('entering upload_file')
        try:
            (filename, md5_hash) = upload_queue.get(block=False)
        except queue_exception.Empty:
            logger.debug('queue is empty, caught EMPTY')
            return

        logger.debug('trying to upload %s', filename)
        upload_url, response_code, md5 = self.get_upload_url(filename)
        logger.debug("upload url is '%s'", upload_url)
        if response_code == 200:
            logger.debug('uploading file %s', filename)
            try:
                logger.info("Uploading file: %s", filename)
                response = self.do_upload(upload_url, "PUT", md5, filename)
                logger.debug('finished uploading %s', filename)
            except Exception, e:
                logger.error('could not do upload for %s', filename)
                logger.error(traceback.format_exc())
                raise e

        if common.SIGINT_EXIT:
            logger.debug("Exiting Upload thread")
            return

        if upload_queue.empty():
            logger.debug('upload_queue is empty')
            return None
        else:
            logger.debug('upload_queue is not empty')

            self.upload_file(upload_queue)

        return


    def do_upload(self, upload_url, http_verb, md5, filename):
        # h = Http()
        # this header is needed to work with signed urls
        headers={
            'Content-Type': 'application/octet-stream',
            'Content-MD5': md5,
        }
        data = open(filename, 'rb')
        response = common.retry(lambda:  requests.put(upload_url, data=data, headers=headers))
        # resp, content = h.request(upload_url, http_verb, upload_buffer, headers=headers)
        # TODO: verify upload
        return resp, content


    def main(self):
        logger.info('Starting Uploader...')

        while not common.SIGINT_EXIT:
            try:
                data = {}
                data['location'] = self.location
                logger.debug("Data: %s", data)
                resp_str, resp_code = self.api_client.make_request('/uploads/client/next',
                                                                   data=json.dumps(data),  # TODO: pass content type correctly in api_client
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
                self.run_uploads(upload_files)
                logger.info('done uploading files')

                finish_dict = {'upload_id':upload_id}

                if upload_files:
                    finish_dict['status'] = 'server_pending'
                else:
                    finish_dict['status'] = 'success'
                resp_str, resp_code = self.api_client.make_request('/uploads/%s/finish' % upload_id,
                                                                 data=json.dumps(finish_dict),
                                                                 verb='PUT')

            except Exception, e:
                logger.error('hit exception %s', e)
                logger.error(traceback.format_exc())
                time.sleep(self.sleep_time)
                continue

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
