import base64
import hashlib
import multiprocessing
import Queue as queue_exception
import threading
import traceback

from httplib2 import Http

import conductor, conductor.setup

from conductor.setup import *
from conductor.lib import api_client, common



class Uploader():
    def __init__(self, args=None):
        logger.debug("Uploader.__init__")
        self.api_client = conductor.lib.api_client.ApiClient()

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
        return response_string

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

        process_count = CONFIG['thread_count']
        uploaded_queue = multiprocessing.Queue()
        upload_queue = multiprocessing.Queue()
        for upload_file in file_list:
            logger.debug('adding %s to queue', upload_file)
            upload_queue.put(upload_file)

        threads = []
        for n in range(process_count):

            thread = threading.Thread(target=self.upload_file, args=(upload_queue, uploaded_queue))

            thread.start()
            threads.append(thread)

        for idx, thread in enumerate(threads):
            logger.debug('waiting for thread: %s', idx)
            thread.join()

        logger.debug('done with threading stuff')
        uploaded_list = []
        while not uploaded_queue.empty():
            uploaded_list.append(uploaded_queue.get())

        return uploaded_list


    def upload_file(self, upload_queue, uploaded_queue):
        logger.debug('entering upload_file')
        try:
            filename = upload_queue.get(block=False)
        except queue_exception.Empty:
            logger.debug('queue is empty, caught EMPTY')
            return

        logger.debug('trying to upload %s', filename)
        upload_url = self.get_upload_url(filename)
        logger.debug("upload url is '%s'", upload_url)
        if upload_url is not '':
            logger.debug('uploading file %s', filename)
            try:
                resp, content = common.retry(lambda: self.do_upload(upload_url, "POST", open(filename, 'rb')))
                uploaded_queue.put(filename)
                logger.debug('finished uploading %s', filename)
            except Exception, e:
                logger.error('could not do upload for %s', filename)
                logger.error(traceback.format_exc())
                raise e

        if upload_queue.empty():
            logger.debug('upload_queue is empty')
            return None
        else:
            logger.debug('upload_queue is not empty')

            self.upload_file(upload_queue, uploaded_queue)


        return


    def do_upload(self, upload_url, http_verb, upload_buffer):
        h = Http()
        resp, content = h.request(upload_url, http_verb, upload_buffer)
        return resp, content
