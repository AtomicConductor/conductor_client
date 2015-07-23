import base64
import json
import hashlib
from httplib2 import Http
import multiprocessing
import Queue as queue_exception
import sys
import threading
import time
import traceback

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
        common.register_sigint_signal_handler()

    def get_upload_url(self, filename):
        uri_path = '/api/files/get_upload_url'
        # TODO: need to pass md5 and filename
        params = {
            'filename': filename,
            'md5': self.get_base64_md5(filename)
        }
        logger.debug('params are %s', params)
        response_string, response_code = self.api_client.make_request(uri_path=uri_path, params=params)
        # TODO: validate that no error occured via error code
        return response_string, response_code

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


    def run_uploads(self, file_list):
        if not file_list:
            logger.debug("No files to upload. Skipping run_uploads")
            return []

        upload_queue = multiprocessing.Queue()
        for upload_file in file_list:
            logger.debug('adding %s to queue', upload_file)
            upload_queue.put(upload_file)

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
            filename = upload_queue.get(block=False)
        except queue_exception.Empty:
            logger.debug('queue is empty, caught EMPTY')
            return

        logger.debug('trying to upload %s', filename)
        upload_url, response_code = self.get_upload_url(filename)
        logger.debug("upload url is '%s'", upload_url)
        if response_code == 200:
            logger.debug('uploading file %s', filename)
            try:
                logger.info("Uploading file: %s", filename)
                resp, content = common.retry(lambda: self.do_upload(upload_url, "POST", open(filename, 'rb')))
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


    def do_upload(self, upload_url, http_verb, upload_buffer):
        h = Http()
        resp, content = h.request(upload_url, http_verb, upload_buffer)
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







