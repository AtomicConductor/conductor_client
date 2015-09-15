#!/usr/bin/env python

""" Command Line Process to run downloads.
"""

import argparse
import collections
import imp
import json
import os
import multiprocessing
import ntpath
import requests
import sys
import time
import threading
import traceback

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from conductor.lib import common, api_client, worker
from conductor.setup import logger, CONFIG

CHUNK_SIZE = 1024


class DownloadWorker(worker.ThreadWorker):
    def do_work(self, job):
        url  = job['url']
        path = job['path']
        md5  = job['md5']
        size = job['size']

        if not self.correct_file_present(path, md5):
            self.metric_store.increment('bytes_to_download', size)
            common.retry(lambda: self.download_file(url, path))

    def download_file(self, download_url, path):
        request = requests.get(download_url, stream=True)
        with open(path, 'wb') as file_pointer:
            for chunk in requests.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    file_pointer.write(chunk)
                    self.metric_store.increment('bytes_downloaded', len(chunk))
        return True

    def correct_file_present(self, path, md5):
        if not os.path.isfile(path):
            return false

        if not md5 == common.get_base64_md5(path):
            return false

        return true

class ReportThread(worker.Reporter):
    def report_status(self, download_id):
        ''' update status of download '''
        post_dic = {
            'download_id': download_id,
            'status': 'downloading',
            'bytes_downloaded': self.metric_store.get('bytes_downloaded'),
            'bytes_to_download': self.metric_store.get('bytes_to_download'),
        }
        response_string, response_code = self.api_helper.make_request('/downloads/status', data=json.dumps(post_dic))
        logger.debug("updated status: %s\n%s", response_code, response_string)
        return response_string, response_code


    def start(self, download_id):
        while self.working:
            self.report_status(download_id)
            time.sleep(10)


class Download(object):
    naptime = 15
    def __init__(self, args):
        self.job_id = args.get('job_id')
        self.task_id = args.get('task_id')
        self.output_path = args.get('output')
        logger.info("output path=%s, job_id=%s, task_id=%s" % \
            (self.output_path, self.job_id, self.task_id))
        self.location = args.get("location") or CONFIG.get("location")
        self.thread_count = CONFIG['thread_count']
        self.api_helper = api_client.ApiClient()
        common.register_sigint_signal_handler()

    def handle_respnse(self, download_id, downloads):
        manager = self.create_manager(download_id)
        for download in downloads:
            manager.add_task(download)
        job_output = manager.join()
        if job_output == True:
            # report success
            return True
        # report failure
        return False

    def create_manager(self, download_id):
        job_description = collections.OrderedDict([
            (DownloadWorker, self.thread_count),
        ])
        reporter_description = [(ReportThread, download_id)]
        manager = worker.JobManager(job_description, reporter_description)
        manager.start()
        return manager

    def nap(self):
        if not common.SIGINT_EXIT:
            time.sleep(self.naptime)

    def main(self):
        logger.info('starting downloader...')
        while not common.SIGINT_EXIT:
            try:
                download_id, downloads = self.get_next_download()
                self.handle_respnse(download_id, downloads)
            except:
                logger.error('hit uncaught exception:')
                logger.error(traceback.format_exc())
            finally:
                self.nap()
        return

    def get_next_download(job_id=None, task_id=None):
        try:
            if job_id:
                endpoint = '/downloads/%s' % job_id
            else:
                endpoint = '/downloads/next'

            if task_id:
                if not job_id:
                    raise ValueError("you need to specify a job_id when passing a task_id")
                params = {'tid': task_id}
            else:
                params = None

            json_data = json.dumps({'location': self.location})
            response_string, response_code = self.api_helper.make_request(endpoint, data=json_data, params=params)
            logger.debug("response code is:\n%s" % response_code)
            logger.debug("response data is:\n%s" % response_string)

            if response_code != 201:
                return None

            download_job = json.loads(response_string)
            download_id = download_job['download_id']
            downloads = download_job['downloads']

            return download_id, downloads

        except:
            logger.error('could not get next download:')
            logger.error(traceback.format_exc())
            return None


def run_downloader(args):
    '''
    Start the downloader process. This process will run indefinitely, polling
    the Conductor cloud app for files that need to be downloaded.
    '''
    # convert the Namespace object to a dictionary
    args_dict = vars(args)
    logger.debug('Downloader parsed_args is %s', args_dict)

    downloader = Download(args_dict)
    downloader.main()

if __name__ == "__main__":
    run_downloader()
