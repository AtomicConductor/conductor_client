#!/usr/bin/env python

""" Command Line Process to run downloads.
"""

import argparse
import collections
import errno
import imp
import json
import os
import multiprocessing
import ntpath
import re
import requests
import sys
import time
import threading
import traceback
from Queue import Queue

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from conductor.lib import common, api_client, worker
from conductor.setup import logger, CONFIG

CHUNK_SIZE = 1024

shutdown_event = threading.Event()

class DownloadWorker():
    def __init__(self, q, output_path, i):
        self.q = q
        self.output_path = output_path
        self.thread_num = i
        self.api_helper = api_client.ApiClient()

    def do_work(self):
        # while not common.SIGINT_EXIT:
        while not shutdown_event.is_set():
            if self.q.qsize() > 0:
                logger.debug("Getting next download...")
                job = self.q.get()
                try:
                    self.do_download(job)
                except Exception, e: 
                    error_message = traceback.format_exc()
                    logger.error('Thread %d hit error: %s\n' % (self.thread_num, error_message))
            else:
                logger.debug("No downloads found in queue. Sleeping...")
                time.sleep(5)
        logger.debug("Thread %d got shutdown event!" % self.thread_num)

    def do_download(self, download_data):
        logger.debug('Thread %d got file to download:' % self.thread_num)
        for job in download_data['files']:
            url = job['url']
            path = job['path']
            md5 = job['md5']
            size = int(job['size'])

            logger.debug('\turl is %s', url)
            logger.debug('\tpath is %s', path)
            logger.debug('\tmd5 is %s', md5)
            logger.debug('\tsize is %s', size)

            if self.output_path:
                logger.debug('using output_path %s', path)
                path = re.sub(download_data['destination'], self.output_path, path)
                logger.debug('set new path to: %s', path)

            if not self.correct_file_present(path, md5):
                logger.debug('downloading file...')
                # self.metric_store.increment('bytes_to_download', size)
                common.retry(lambda: self.download_file(url, path))
                logger.debug('file downloaded')
            else:
                logger.debug('file already exists')

        #  When the job is done, phone home and mark as complete
        self.report_status("downloaded", download_data['download_id'])

    def report_status(self, status, download_id=None):
        if not download_id:
            logger.debug("not reporting status as we weren't passed a download_id")
            return None

        ''' update status of download '''
        post_dic = {
            'download_id': download_id,
            'status': status,
        }
        logger.debug('marking download %s as %s', download_id, status)
        response_string, response_code = self.api_helper.make_request('/downloads/status', data=json.dumps(post_dic))
        logger.debug("updated status: %s\n%s", response_code, response_string)
        return response_string, response_code

    def download_file(self, download_url, path):
        self.safe_mkdirs(os.path.dirname(path))
        logger.debug('trying to download %s', path)
        print("Downloading %s" % path)
        total_downloaded = 0
        request = requests.get(download_url, stream=True)
        with open(path, 'wb') as file_pointer:
            count = 0
            for chunk in request.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    total_downloaded += CHUNK_SIZE
                    file_pointer.write(chunk)
                    count += 1
                    if count % 1000 == 0:
                        print("%s - %d bytes" % (path, total_downloaded))
                    # self.metric_store.increment('bytes_downloaded', len(chunk))
        print('Successfully downloaded %s' % (path))
        logger.debug('setting file perms to 666')
        os.chmod(path, 0666)

        return True

    def safe_mkdirs(self, dirpath):
        '''
        Create the given directory.  If it already exists, suppress the exception.
        This function is useful when handling concurrency issues where it's not
        possible to reliably check with a directory exists before creating it.
        '''
        try:
            os.makedirs(dirpath)
        except OSError:
            if not os.path.isdir(dirpath):
                raise

    def correct_file_present(self, path, md5):
        logger.debug('checking if %s exists and is uptodate at %s', path, md5)
        if not os.path.isfile(path):
            logger.debug('file does not exist')
            return False

        if not md5 == common.get_base64_md5(path):
            logger.debug('md5 does not match')
            return False

        logger.debug('file is uptodate')
        return True


class Download(object):
    naptime = 15
    def __init__(self, args):
        logger.debug('args are: %s', args)

        self.job_id = args.get('job_id')
        self.task_id = args.get('task_id')
        self.output_path = args.get('output')
        logger.info("output path=%s, job_id=%s, task_id=%s" % \
            (self.output_path, self.job_id, self.task_id))
        self.location = args.get("location") or CONFIG.get("location")
        self.thread_count = CONFIG['thread_count']
        self.api_helper = api_client.ApiClient()
        self.queue = Queue()
        self.threads = []
        common.register_sigint_signal_handler()

    def nap(self):
        if not common.SIGINT_EXIT:
            time.sleep(self.naptime)

    def main(self, job_ids=None):
        logger.info('starting downloader...')

        self.start_threads()

        #  If job ids were specified, immediately proceed to the download
        if job_ids:
            for job_id in job_ids:
                #  Get download files
                logger.debug("Finding downloads for job %s" % job_id)
                self.download_job(job_id)
            self.wait_for_threads()
            return

        #  Find jobs that need to be downloaded
        print("Waiting for downloads...")
        while not common.SIGINT_EXIT:
            logger.debug("Finding next download")
            next_download = self.find_download()
            if next_download:
                logger.debug("Found download %s" % next_download['download_id'])
                self.start_download(next_download)
            else:
                self.nap()

        print("\nGot exit signal, waiting for threads to finish...\n")
        self.wait_for_threads()
                
    def wait_for_threads(self):
        time.sleep(5)
        shutdown_event.set()

    def start_threads(self):
        for i in range(self.thread_count):
            logger.debug("Starting thread %d" % i)
            worker = DownloadWorker(self.queue, self.output_path, i)
            self.threads.append(threading.Thread(target=worker.do_work))
            self.threads[i].setDaemon(True)
            self.threads[i].start()

    def start_download(self, download_data):
        logger.debug("Adding download %s to queue" % download_data['download_id'])
        if self.job_id:
            for download in download_data['downloads']:
                self.queue.put(download)
        else:
            self.queue.put(download_data)

    #  Download the files for a particular job
    def download_job(self, job_id):
        endpoint = '/downloads/%s' % job_id
        params = None
        if self.task_id:
            params = {'tid': self.task_id}

        #  Query download data
        download_job = self.query_downloads(endpoint, params)

        self.start_download(download_job)

    #  Find the next job to download
    def find_download(self):
        endpoint = '/downloads/next'
        params = None

        return self.query_downloads(endpoint, params)

    #  Query the back end for the download data
    def query_downloads(self, endpoint, params):

        json_data = json.dumps({'location': self.location})
        logger.debug('Querying %s' % endpoint)
        logger.debug('json_data is: %s', json_data)
        response_string, response_code = self.api_helper.make_request(endpoint, data=json_data, params=params)
        logger.debug("response code is:\n%s" % response_code)
        logger.debug("response data is:\n%s" % response_string)

        if response_code != 201:
            return None

        download_job = json.loads(response_string)

        return download_job

#  Do a little argument validation
def validate_args(args_dict):
    if args_dict.get('task_id') and not args_dict.get('job_id'):
        print("Error: a job id must be specified with a task id!")
        return False
    return True

def run_downloader(args):
    '''
    Start the downloader process. This process will run indefinitely, polling
    the Conductor cloud app for files that need to be downloaded.
    '''
    # convert the Namespace object to a dictionary
    args_dict = vars(args)
    logger.debug('Downloader parsed_args is %s', args_dict)

    if not validate_args(args_dict):
        return

    downloader = Download(args_dict)
    downloader.main(job_ids=args_dict.get('job_id'))

if __name__ == "__main__":
    # exit(1)
    print 'args are %s' % args
    run_downloader(args)
