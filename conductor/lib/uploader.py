import base64
import time
import ast
import json
import hashlib
from httplib2 import Http
import multiprocessing
import Queue
import sys
from threading import Thread
import time
import traceback
import requests

from conductor.setup import CONFIG, logger
from conductor.lib import api_client, common

class Worker():
    def __init__(self, in_queue, out_queue):
        self.in_queue = in_queue
        self.out_queue = out_queue

    def do_work(self,job):
        raise NotImplementedError

    def target(self):
        print 'on target'
        while True:
            try:
                print 'looking for work'
                job = self.in_queue.get(True)
                print 'got job!'
                output = self.do_work(job)
                self.out_queue.put(output)
                self.in_queue.task_done()
            except Exception:
                # print 'hit exception: %s' % e
                print traceback.print_exc()
                print traceback.format_exc()

    def start(self,number_of_threads=1):
        print 'in start'
        print 'number_of_threads is %s' % number_of_threads
        for i in range(number_of_threads):
            print 'starting thread'
            thd = Thread(target = self.target)
            thd.daemon = True
            thd.start()
            print 'done starting thread'

class MD5Worker(Worker):
        def __init__(self, in_queue, out_queue):
            logger.debug('starting init for MD5Worker')
            Worker.__init__(self, in_queue, out_queue)

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
            out_queue.put((filename, md5))


class MD5OutputWorker(Worker):
    def __init__(self, in_queue, out_queue):
        logger.debug('starting init for MD5OutputWorker')
        Worker.__init__(self, in_queue, out_queue)


    def target(self):
        batch={}
        def ship_batch():
            if batch:
                out_queue.put(batch)
                batch = {}

        while True:
            try:
                # block on the queue with a 5 second timeout
                file_md5_tuple = in_queue.get(True, 5)
                batch[file_md5_tuple[0]] = file_md5_tuple[1]
                if len(batch) == self.batch_size:
                    ship_batch()
                # mark this task as done
                in_queue.task_done()
            except Queue.Empty:
                ship_batch()


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
            for path, upload_url in url_list.iteritems():
                self.out_queue.put((path,upload_url))
            else:
                logger.error('response code was %s' % response_code)


class UploadWorker(Worker):
    def __init__(self, in_queue, out_queue):
        logger.debug('starting init for HttpBatchWorker')
        Worker.__init__(self, in_queue, out_queue)


    def do_work(self, job):
        filename = job[0]
        upload_url = job[1]

        logger.info("Uploading file: %s", filename)
        # TODO: where does md5 come from?
        response = self.do_upload(upload_url, "PUT", md5, filename)
        logger.debug('finished uploading %s', filename)


class Uploader():

    sleep_time = 10

    def __init__(self, args=None):
        logger.debug("Uploader.__init__")
        self.api_client = api_client.ApiClient()
        args = args or {}
        self.location = args.get("location") or CONFIG.get("location")
        self.process_count = CONFIG['thread_count']
        self.batch_size = 100 # the controlls the batch size for http get_signed_urls
        common.register_sigint_signal_handler()

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

    # TODO: optimize blocksize




    def load_md5_process_queue(self, md5_process_queue, file_list):
        '''
        Add all items in the file_list to the md5_process_queue so workers can
        work off the queue
        '''
        for upload_file in file_list:
            logger.debug('adding %s to queue', upload_file)
            md5_process_queue.put(upload_file)


    def create_worker_pools(self)
        # create input and output for the md5 workers
        md5_process_queue = multiprocessing.Queue()
        md5_output_queue = multiprocessing.Queue()
        http_batch_queue = multiprocessing.Queue()
        signed_upload_url_queue = multiprocessing.Queue()
        finished_queue = multiprocessing.Queue()

        # create md5 worker pool threads
        md5_worker = MD5Worker(md5_process_queue, md5_output_queue)
        md5_worker.start(self.process_count)


        # create md5 output worker
        md5_output_worker = MD5OutputWorker(md5_output_worker,http_batch_queue)
        md5_output_worker.start()


        # creat http batch worker
        http_batch_worker = HttpBatchWorker(httpbatchworker, signed_upload_url_queue)
        http_batch_worker.start(self.process_count/4) # TODO: consider thread count


        # create upload workers
        upload_worker = UploadWorker(signed_upload_url_queue, finished_queue)
        upload_worker.start(self.process_count)


        logger.debug('done creating worker pools')
        return [
            md5_process_queue,
            md5_output_queue,
            http_batch_queue,
            signed_upload_url_queue,
            finished_queue,
        ]

        # kill rest
    def run_uploads(self, file_list):

        upload_queue = multiprocessing.Queue()
        for upload_file in file_dict:
            logger.debug('adding %s:%s to queue' % (upload_file, file_dict[upload_file]))
            upload_queue.put((upload_file, file_dict[upload_file]))

        threads = []
        for n in range(self.process_count):

            thread = Thread(target=self.upload_file, args=(upload_queue,))

            thread.start()
            threads.append(thread)

        for idx, thread in enumerate(threads):
            logger.debug('waiting for thread: %s', idx)
            thread.join()
        logger.debug('done with threading stuff')



    def upload_file(self, upload_queue):
        logger.debug('entering upload_file')
        try:
            filename = upload_queue.get(block=False)
        except Queue.Empty:
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
        logger.info('creating worker pools...')
        self.create_worker_pools()

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

                # load upload_file list to begin processing
                work_queues = self.load_md5_process_queue(self, self.md5_process_queue, upload_files):
                md5_process_queue = work_queues[0]
                md5_output_queue = work_queues[1]
                http_batch_queue = work_queues[2]
                signed_upload_url_queue = work_queues[3]
                finished_queue = work_queues[4]

                # wait for work to finish
                md5_process_queue.join()
                md5_output_queue.join()
                http_batch_queue.join()
                signed_upload_url_queue.join()


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

    # wait for work to finish
    md5_process_queue.join()
    md5_output_queue.join()
    http_batch_queue.join()
    signed_upload_url_queue.join()

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
