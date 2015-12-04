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

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from conductor.lib import common, api_client, worker
from conductor.setup import logger, CONFIG

CHUNK_SIZE = 1024


class DownloadWorker(worker.ThreadWorker):
    def __init__(self, *args, **kwargs):
        logger.debug('args are %s', args)
        logger.debug('kwargs are %s', kwargs)

        worker.ThreadWorker.__init__(self, *args, **kwargs)
        self.output_path = kwargs.get('output_path')
        self.api_helper = api_client.ApiClient()

    def report_error(self, download_id, error_message):
        try:
            logger.error('failing upload due to: \n%s' % error_message)
            # report error_message to the app
            resp_str, resp_code = self.api_helper.make_request(
                '/downloads/%s/fail' % download_id,
                data=error_message,
                verb='POST')
        except e:
            pass
        return True

    def do_work(self, job):
        try:
            download_id = 0
            download_id = job.get('download_id', 0)
            self._do_work(job)
        except Exception, e:
            error_message = traceback.format_exc()
            error_message += traceback.print_exc()
            logger.error('hit error:')
            logger.error(error_message)
            self.report_error(download_id, error_message)

    def _do_work(self, job):
        download_id = job['download_id']
        files = job['files']
        destination = job['destination']
        done = [False]
        bytes_downloaded = [0]
        total_size = 0
        for file in files:
            total_size += file['size']

        reporter = threading.Thread(target=self.report_loop, args=(download_id, total_size, bytes_downloaded, done))
        reporter.daemon = True
        reporter.start()

        for file_info in files:
            logger.debug("file_info: %s", file_info)
            url = file_info['url']
            path = file_info['path']
            md5 = file_info['md5']

            if self.output_path:
                logger.debug('using output_path %s', self.output_path)
                path = re.sub(destination, self.output_path, path)
                logger.debug('set new path to: %s', path)

            self.process_download(path, url, md5, bytes_downloaded)

        done[0] = True
        logger.debug('waiting for reporter thread')
        reporter.join()

    def process_download(self, path, url, md5, bytes_downloaded):
        '''
        For the given file information, download the file to disk.  Check whether
        the file already exists and matches the expected md5 before downloading.
        '''
        logger.debug('checking for existing file %s', path)

        # If the file already exists on disk
        if os.path.isfile(path):
            local_md5 = common.get_base64_md5(path)
            # If the local md5 matchs the expected md5 then no need to download. Skip to next file
            if md5 == local_md5:
                logger.info('Existing file is up to date: %s', path)
                return

            logger.debug('md5 does not match existing file: %s vs %s', md5, local_md5)

            logger.debug('Deleting dirty file: %s', path)
            common.retry(lambda: os.remove(path))

        # download the file
        common.retry(lambda: download_file(url, path, bytes_downloaded))

        # Set file permissions
        logger.debug('setting file perms to 666')
        os.chmod(path, 0666)


    def report_loop(self, download_id, total_size, bytes_downloaded, done):
        while True:
            logger.debug('bytes_downloaded is %s' % bytes_downloaded)
            logger.debug('done is %s' % done)
            if done[0]:
                # mark download as finished
                post_dic = {
                    'download_id': download_id,
                    'status': 'downloaded',
                    'bytes_downloaded': bytes_downloaded[0]
                }
                logger.debug('marking download %s as finished', download_id)
                response_string, response_code = self.api_helper.make_request('/downloads/status', data=json.dumps(post_dic))
                logger.debug("updated status: %s\n%s", response_code, response_string)
                return
            if common.SIGINT_EXIT:
                # mark download as pending
                post_dic = {
                    'download_id': download_id,
                    'status': 'pending',
                }
                logger.debug('marking download %s as pending', download_id)
                response_string, response_code = self.api_helper.make_request('/downloads/status', data=json.dumps(post_dic))
                logger.debug("updated status: %s\n%s", response_code, response_string)
                return

            self.report(download_id, total_size, bytes_downloaded)
            for i in range(0, 9):
                if not done[0] and not common.SIGINT_EXIT:
                    time.sleep(1)

    def report(self, download_id, total_size, bytes_downloaded):
        post_dic = {
            'download_id': download_id,
            'status': 'downloading',
            'bytes_downloaded': bytes_downloaded[0],
            'bytes_to_download': total_size,
        }
        response_string, response_code = self.api_helper.make_request('/downloads/status', data=json.dumps(post_dic))
        logger.debug("updated status: %s\n%s", response_code, response_string)
        return response_string, response_code


def download_file(download_url, path, bytes_downloaded):
    mkdir_p(os.path.dirname(path))
    logger.info('Downloading: %s', path)
    request = requests.get(download_url, stream=True)
    with open(path, 'wb') as file_pointer:
        for chunk in request.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                file_pointer.write(chunk)
                bytes_downloaded[0] += len(chunk)
    request.raise_for_status()
    logger.debug('Successfully downloaded: %s', path)


def mkdir_p(path):
    # return True if the directory already exists
    if os.path.isdir(path):
        return True

    # if parent dir does not exist, create that first
    base_dir = os.path.dirname(path)
    if not os.path.isdir(base_dir):
        mkdir_p(base_dir)

    # create path (parent should already be created)
    try:
        os.mkdir(path)
    except OSError:
        pass

    # make path world writable
    os.chmod(path, 0777)

    return True



class Download(object):
    naptime = 15
    def __init__(self, args):
        logger.debug('args are: %s', args)

        self.job_id = args.get('job_id')
        self.daemon = False if self.job_id else True
        self.task_id = args.get('task_id')
        self.output_path = args.get('output')
        logger.info("output path=%s, job_id=%s, task_id=%s" % \
            (self.output_path, self.job_id, self.task_id))
        self.location = args.get("location") or CONFIG.get("location")
        self.thread_count = CONFIG['thread_count']
        self.api_helper = api_client.ApiClient()
        common.register_sigint_signal_handler()
        self.max_queue_size = self.thread_count

    def create_manager(self):
        args = []
        kwargs = {'thread_count': self.thread_count,
                'output_path': self.output_path}
        job_description = [
            (DownloadWorker, args, kwargs)
        ]
        manager = worker.JobManager(job_description)
        manager.start()
        return manager

    def nap(self):
        if not common.SIGINT_EXIT:
            time.sleep(self.naptime)

    def print_queue_info(self):
        while True:
            logger.info('queue contains %s items' % self.manager.work_queues[0].qsize())
            time.sleep(10)

    def main(self, job_ids=None):
        logger.info('started downloader...')
        self.manager = self.create_manager()
        printer = threading.Thread(target=self.print_queue_info)
        printer.daemon = True
        printer.start()
        if job_ids:
            for jid in job_ids:
                logger.debug('getting download for job %s', jid)
                job_info = self.get_next_download(job_id=jid, task_id=self.task_id)
                if not job_info:
                    error_message = 'could not get download info for job_id %s ' % jid
                    if self.task_id:
                        error_message += 'task_id: %s ' % self.task_id
                    error_message += 'Is this a valid job?'
                    logger.error(error_message)
                    next
                for download in job_info['downloads']:
                    self.manager.add_task(download)
            self.manager.join()
            logger.debug('downloads finished')
        else:
            logger.debug('running downloader daemon')
            self.loop()

    def loop(self):
        while not common.SIGINT_EXIT:
            try:
                self.do_loop()
            except Exception, e:
                logger.error('hit uncaught exception: \n%s', e)
                logger.error(traceback.format_exc())
                self.nap()

    def do_loop(self):
        # don't add more than self.max_queue_size items on the queue
        if self.manager.work_queues[0].qsize() >= self.max_queue_size:
            logger.debug('queue is full at %s items. not adding any more tasks' % self.max_queue_size)
            self.nap()
            return

        next_download = self.get_next_download()
        if not next_download:
            logger.debug('no downloads. sleeping...')
            self.nap()
            return

        self.manager.add_task(next_download)

    def get_next_download(self, job_id=None, task_id=None):
        logger.debug('in get next download')
        try:
            if job_id:
                endpoint = '/downloads/%s' % job_id
            else:
                endpoint = '/downloads/next'

            logger.debug('endpoint is %s', endpoint)
            if task_id:
                if not job_id:
                    raise ValueError("you need to specify a job_id when passing a task_id")
                params = {'tid': task_id}
            else:
                params = None
            logger.debug('params is: %s', params)

            json_data = json.dumps({'location': self.location})
            logger.debug('json_data is: %s', json_data)
            response_string, response_code = self.api_helper.make_request(endpoint, data=json_data, params=params)
            logger.debug("response code is:\n%s" % response_code)
            logger.debug("response data is:\n%s" % response_string)

            if response_code != 201:
                return None

            download_job = json.loads(response_string)

            return download_job

        except Exception, e:
            logger.error('could not get next download: \n%s', e)
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
    downloader.main(job_ids=args_dict.get('job_id'))

if __name__ == "__main__":
    exit(1)
    print 'args are %s' % args
    run_downloader(args)
