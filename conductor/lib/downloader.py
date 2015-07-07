#!/usr/bin/env python

""" Command Line Process to run downloads.
"""

import argparse
import httplib2
import time
import imp
import json
import os
import multiprocessing
import Queue as queue_exception
import random
import sys
import threading
import time
import traceback
import urllib2
import ntpath

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import conductor
import conductor.setup
import conductor.lib.common
import conductor.lib.api_client

from conductor.lib.common import EXIT as EXIT

# Global logger and config objects
logger = conductor.setup.logger
CONFIG = conductor.setup.CONFIG


# we need a place to handle posting the current download status to the app
class DownloadStatus(object):
    def __init__(self):
        self.jobs = {}
        self.api_helper = conductor.lib.api_client.ApiClient()

    def add_job(self, job_id, download_urls):
        self.jobs[job_id] = {'download_urls': download_urls}

    def finish_download(self, job_id, download_url):
        self.jobs[job_id]['download_urls'].pop(download_url)
        if not self.jobs[job_id]['download_urls']:
            self.set_download_status(job_id, 'downloaded')
            self.jobs.pop(job_id, None)

    # if we haven't upated in 60 seconds (or at all), update status
    def mark_in_progress(self, job_id):
        last_mark = self.jobs[job_id].get('last_mark')
        tick = time.time()
        if not last_mark or (tick - last_mark) > 60:
            self.set_download_status(job_id, 'downloading')
            self.jobs[job_id]['last_mark'] = tick

    def set_download_status(self, job_id, status):
        ''' update status of download '''
        post_dic = {
            'download_id': job_id,
            'status': status
        }
        response_string, response_code = self.api_helper.make_request('/downloads/status', data=json.dumps(post_dic))
        logger.info("updated status: %s\n%s", response_code, response_string)
        return response_string, response_code


class Download(object):
    def __init__(self, args):
        self.parser = argparse.ArgumentParser(description=self.__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter)
        self.naptime = 15
        self.DownloadStatus = DownloadStatus()
        self.job_id = args.get('job_id')
        self.output_path = args.get('output')
        print("jid = %s, output = %s" % (self.job_id, self.output_path))


    def main(self):
        logger.info('starting downloader...')

        # initializers
        self.api_helper = conductor.lib.api_client.ApiClient()
        thread_count = CONFIG['thread_count']
        threads = []

        # generate thread worker pool
        self.download_queue = multiprocessing.Queue()
        for i in range(thread_count):
            thread = threading.Thread(
                target=self.download_thread_loop)
            thread.start()
            threads.append(thread)

        # do work until global EXIT is set
        while not conductor.lib.common.EXIT:
            # if there is work queued that hasn't started, don't get more work
            if not self.download_queue.empty():
                self.nap()
                continue

            download_id = None
            # try to get another download to run
            try:
                response_string, response_code = self.get_download()
            except Exception, e:
                logger.error("Failed to get download! %s" % e)
                logger.error(traceback.format_exc())
                self.nap()
                continue

            try:
                logger.debug("beginging download loop")
                if response_code == 201:
                    try:
                        resp_data = json.loads(response_string)
                        logger.debug("response data is:\n" + str(resp_data))
                    except Exception, e:
                        logger.error("Response from server was not json! %s" % e)
                        logger.error(traceback.format_exc())
                        self.nap()
                        continue

                    #  If an individual job id was specified, don't do any 
                    #  status update type things
                    if not self.job_id:
                        download_id = resp_data['download_id']
                        self.DownloadStatus.add_job(download_id, resp_data['download_urls'])
                    
                    for download_url, local_path in resp_data['download_urls'].iteritems():
                        file_path = local_path

                        #  Add support for overriding the output path
                        if self.output_path:
                            dirname, filename = ntpath.split(local_path)
                            if not filename:
                                filename = ntpath.basename(dirname)
                            file_path = os.path.join(self.output_path, filename)

                        #  If a job id was specified on the command line, this
                        #  a manual download. Do not update the database object
                        #  status...
                        update_status = True
                        if self.job_id:
                            update_status = False
                        download_info = [download_url, file_path, download_id, update_status]
                        logger.debug("adding %s to download queue", download_info)
                        self.download_queue.put(download_info)

                    #  Do not run as a daemon if self.job_id was specified...
                    if self.job_id:
                        conductor.lib.common.EXIT = True
                else:
                    logger.debug("nothing to download. sleeping...")
                    sys.stdout.write('.')
                    self.nap()
            except Exception, e:
                logger.error("caught exception %s" % e)
                logger.error(traceback.format_exc())
                # Please include this sleep, to ensure that the Conductor
                # does not get flooded with unnecessary requests.
                self.nap()

        # this will only run if common.EXIT is set
        for i in range(thread_count):
            self.download_queue.put(None)

        for idx, thread in enumerate(threads):
            logger.debug('waiting for thread: %s', idx)
            thread.join()


    def get_download(self):
        ''' get a new file to download from the server or 404 '''
        if self.job_id:
            response_string, response_code = \
                self.api_helper.make_request('/downloads/%s' % (self.job_id))
        else:
            response_string, response_code = self.api_helper.make_request('/downloads/next')
    
        if response_code == '201':
            logger.info("new file to download:\n" + response_string)

        return response_string, response_code

    def download_item(self, download_url, local_path, download_id, update_status):
        logger.debug("downloading: %s to %s", download_url, local_path)
        if not os.path.exists(os.path.dirname(local_path)):
            os.makedirs(os.path.dirname(local_path), 0775)
        CHUNKSIZE = 10485760  # 10MB

        def chunk_report(bytes_so_far, chunk_size, total_size):
            percent = float(bytes_so_far) / total_size
            percent = round(percent * 100, 2)


            logger.info("Downloaded %d of %d bytes (%0.2f%%)\r" %
                        (bytes_so_far, total_size, percent))

            if bytes_so_far >= total_size:
                logger.info('\n')

        def chunk_read(response, update_status, chunk_size=CHUNKSIZE, report_hook=None):
            logger.debug('chunk_size is %s', chunk_size)
            total_size = response.info().getheader('Content-Length').strip()
            total_size = int(total_size)
            bytes_so_far = 0

            download_file = open(local_path, 'wb')
            while 1:
                if update_status:
                    self.DownloadStatus.mark_in_progress(download_id)
                chunk = response.read(chunk_size)
                chunk_size = len(chunk)
                bytes_so_far += chunk_size
                download_file.write(chunk)

                if not chunk:
                    download_file.close()
                    break

                if report_hook:
                    report_hook(bytes_so_far, chunk_size, total_size)

            return bytes_so_far


        response = urllib2.urlopen(download_url)
        chunk_read(response, update_status, report_hook=chunk_report)
        logger.info('downloaded %s', local_path)
        if update_status:
            self.DownloadStatus.finish_download(download_id, download_url)

    # worker loop
    def download_thread_loop(self):
        while not conductor.lib.common.EXIT:
            # get another item to download (blocking)
            download_task = self.download_queue.get()
            if not download_task:
                continue
            download_url, local_path, download_id, update_status = download_task
            # do download
            conductor.lib.common.retry(
                lambda: self.download_item(
                    download_url,
                    local_path,
                    download_id,
                    update_status,
                ),
            )
        return


    def nap(self):
        if not conductor.lib.common.EXIT:
            time.sleep(self.naptime)

def run_downloader(args):
    '''
    Start the downloader process. This process will run indefinitely, polling
    the Conductor cloud app for files that need to be downloaded. 
    '''
    args_dict = vars(args)
    downloader = Download(args_dict)
    downloader.main()

if __name__ == "__main__":
    run_downloader()
