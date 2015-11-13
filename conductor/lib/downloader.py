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
    sys.path.append(os.path.dirname(os.path.dirname(os.path.diraname(os.path.abspath(__file__)))))


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

    def do_work(self, job, thread_int):
        try:
            download_id = 0
            download_id = job.get('download_id', 0)
            self._do_work(job, thread_int)
        except Exception, e:
            error_message = traceback.format_exc()
            error_message += traceback.print_exc()
            logger.error('[thread %s]Hit error:', thread_int)
            logger.error('[thread %s]\n%s', thread_int, error_message)
            self.report_error(download_id, error_message)

    def _do_work(self, job, thread_int):
        download_id = job['download_id']
        files = job['files']
        done = [False]
        bytes_downloaded = [0]
        total_size = 0
        for file_info in files:
            total_size += file_info['size']

        reporter = threading.Thread(target=self.report_loop, args=(download_id, total_size, bytes_downloaded, done, thread_int))
        reporter.daemon = True
        reporter.start()

        for file_info in files:
            logger.debug('[thread %s]Processing file', thread_int)

            url = file_info['url']
            relative_path = file_info['relative_path']
            output_dir = file_info['output_dir']
            md5 = file_info['md5']
            size = int(file_info['size'])

            logger.debug('[thread %s]\turl:%s', thread_int, url)
            logger.debug('[thread %s]\tmd5:%s', thread_int, md5)
            logger.debug('[thread %s]\tsize:%s', thread_int, size)
            logger.debug('[thread %s]\trelative_path:%s', thread_int, relative_path)
            logger.debug('[thread %s]\toutput_dir:%s', thread_int, output_dir)

            if self.output_path:
                logger.debug('[thread %s]\tOverriding output directory to %s', thread_int, self.output_path)
                output_dir = self.output_path

            filepath = os.path.join(output_dir, relative_path)
            logger.debug('[thread %s]\tfilepath: %s', thread_int, filepath)

            logger.debug('[thread %s]\tchecking if file exists and md5 verified: %s', thread_int, filepath)
            if self.correct_file_present(filepath, md5, thread_int):
                logger.debug('[thread %s]\tFile exists and is md5 verified: %s', thread_int, filepath)
            else:
                logger.debug('[thread %s]\tfile must be downloaded: %s', thread_int, filepath)
                common.retry(lambda: self.download_file(url, filepath, bytes_downloaded, thread_int))

        done[0] = True
        logger.debug('[thread %s]\twaiting for reporter thread', thread_int)
        reporter.join()

    def report_loop(self, download_id, total_size, bytes_downloaded, done, thread_int):
        while True:
            logger.debug('[thread %s]bytes_downloaded is %s', thread_int, bytes_downloaded)
            logger.debug('[thread %s]done is %s', thread_int, done)
            if done[0]:
                # mark download as finished
                post_dic = {
                    'download_id': download_id,
                    'status': 'downloaded',
                    'bytes_downloaded': bytes_downloaded[0]
                }
                logger.debug('[thread %s]marking download %s as finished', thread_int, download_id)
                response_string, response_code = self.api_helper.make_request('/downloads/status', data=json.dumps(post_dic))
                logger.debug("[thread %s]updated status: %s\n%s", thread_int, response_code, response_string)
                return
            if common.SIGINT_EXIT:
                # mark download as pending
                post_dic = {
                    'download_id': download_id,
                    'status': 'pending',
                }
                logger.debug('[thread %s]marking download %s as pending', thread_int, download_id)
                response_string, response_code = self.api_helper.make_request('/downloads/status', data=json.dumps(post_dic))
                logger.debug("[thread %s]updated status: %s\n%s", thread_int, response_code, response_string)
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

    def download_file(self, download_url, path, bytes_downloaded, thread_int):
        self.mkdir_p(os.path.dirname(path))
        logger.debug('[thread %s]\ttrying to download: %s', thread_int, path)
        request = requests.get(download_url, stream=True)
        with open(path, 'wb') as file_pointer:
            for chunk in request.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    file_pointer.write(chunk)
                    bytes_downloaded[0] += len(chunk)
        request.raise_for_status()
        logger.debug('[thread %s]\t%s successfully downloaded', thread_int, path)
        logger.debug('[thread %s]\tsetting file perms to 666', thread_int)
        os.chmod(path, 0666)

        return True

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

    def correct_file_present(self, path, md5, thread_int):
        if not os.path.isfile(path):
            logger.debug('[thread %s]\tfile does not exist', thread_int)
            return False

        current_md5 = common.get_base64_md5(path)
        if md5 != current_md5:
            logger.debug('[thread %s]\tmd5s do not match: %s vs %s', thread_int, md5, current_md5)
            return False

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
                params = {'location': self.location}
            logger.debug('params is: %s', params)

            response_string, response_code = self.api_helper.make_request(endpoint, params=params)
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
