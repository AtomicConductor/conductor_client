#!/usr/bin/env python

""" Command Line Process to run downloads.
"""

import imp
import logging
import os
import sys
import signal
import time
import ctypes
import traceback
import multiprocessing
import requests

WORKER_PAUSE_DURATION = 15
DOWNLOAD_CHUNK_SIZE = 2048
MAX_DOWNLOAD_RETRIES = 5
TOUCH_INTERVAL = 1000 # number of DOWNLOAD_CHUNK_SIZE chunks to process before touching file in db.


try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from conductor import CONFIG
from conductor.lib import common, api_client, worker, loggeria

logger = logging.getLogger(__name__)

LOG_FORMATTER = logging.Formatter('%(asctime)s  %(name)s%(levelname)9s  %(threadName)s:  %(message)s')


class DownloadWorker(multiprocessing.Process):
    """
    The DownloadWorker class is a subclass of multiprocessing.Process.
    Its responsibilities are:

      - Ask the downloader service for the next download in the queue.
      - stream the downloadable file to disk.
      - periodically report progress to the servivce.
      - notify service of file completion and failure (when possible)

    A state variable (multiprocessing.Value) is passed into __init__
    that is used to control both the 'next dl' and 'process dl chunks'
    loops. The possible states are:

        - "running":       all systems go.
        - "shutting_down": stop procecssing next files, complete the one in progress.
        - "stopping":      stop everything and cleanup.

    """
    def __init__(self, run_state, account, output_dir="", project=None, location=None):
        """
        Initialize download worker process.

        """
        super(DownloadWorker, self).__init__()
        self._run_state = run_state
        self._chunks = 0
        self._total_size = 0
        self.output_dir = output_dir or ""
        self.location = location or CONFIG.get("location")
        self.account = CONFIG.get("account")

    def run(self):
        "called at Instance.start()"
        info_str = "Starting worker %s - account: %s  location: %s"
        logger.info(info_str, self.name, self.account, self.location)
        while self._run_state.value == "running":
            next_dl = self.get_next_download()
            if next_dl:
                self.maybe_download_file(next_dl)
            else:
                self.wait()
        return

    def get_next_download(self):
        "fetch the next downloadable file, return siugned url."
        result = Backend.next(self.account, location=self.location)
        if result:
            return result[0]
        return {}

    def wait(self):
        "pause between empty get_next_download() calls"
        time.sleep(WORKER_PAUSE_DURATION)

    def maybe_download_file(self, dl_info):
        """
        checks for existing file and validates md5, if valid, skip download
        """
        # TODO: retry mechanism
        url = dl_info["url"]
        logger.info("thread: %s  -  downloading file %s", self.name, url)
        local_file = self.make_local_path(dl_info)
        if not self.file_exists_and_is_valid(local_file, dl_info["download_file"]["md5"]):
            self.start_download(url, local_file, dl_info)
        else:
            logger.warning("file %s already exists and is valid" % local_file)
            Backend.finish(dl_info["id"], bytes_downloaded=self._total_size)
            self.reset()
            return

    def start_download(self, url, local_file, dl_info, try_count=1):
        """
        helper function that wraps _start_download() in try except
        """
        try:
            self._start_download(url, local_file, dl_info)
        except:
            self._handle_download_error(url, local_file, dl_info, try_count)
        else:
            # TODO: validate md5, retry etc
            Backend.finish(dl_info["id"], bytes_downloaded=None)
            self.reset()
            logger.info("finished download of %s" % local_file)
            return local_file

    def _start_download(self, url, local_file, dl_info):
        """
        The actual download loop implementation
        """
        req = requests.get(url, stream=True)
        basedir = os.path.dirname(local_file)
        if not os.path.exists(basedir):
            os.makedirs(basedir)
        try:
            os.remove(local_file)
        except:
            pass
        log_str = "start_download id=%(id)s account=%(account)s project=%(project)s location=%(location)s jid=%(jid)s tid=%(tid)s source=%(source_file)s dest=%(local_file)s "
        dl_info["download_file"]["local_file"]= local_file
        logger.info(log_str % dl_info["download_file"])
        with open(local_file, 'wb') as f:
            for chunk in req.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                if self._run_state.value != "stopping":
                    self._process_file_chunk(f, chunk, dl_info)
                else:
                    print "quit!"
                    # TODO: either mark as failed or clanup and mark as pending?
                    return

    def _handle_download_error(self, url, local_file, dl_info, try_count):
        """
        properly handle errors during download chunk streaming.
        """
        logger.error("download error id=%s file=%s try_count=%s" % (dl_info["id"], local_file, try_count))
        tb = traceback.format_exc()
        print tb
        error = sys.exc_info()[0]
        print error
        self.reset()
        # TODO: proper logging
        # TODO: cancel/stop event cleanup, if any
        if try_count == MAX_DOWNLOAD_RETRIES:
            logger.error("max download tries exceeded file=%s" % local_file)
            Backend.fail(dl_info["id"], bytes_downloaded=self._total_size)
            self.reset()
            return
        else:
            logger.info("retrying download file=%s" % local_file)
            self.start_download(url, local_file, dl_info, try_count=try_count+1)

    def _process_file_chunk(self, file_obj, chunk, dl_info):
        """
        process each chunk in a streaming download.
        """
        file_obj.write(chunk)
        self._chunks += 1
        self._total_size += sys.getsizeof(chunk)
        if not self._chunks % TOUCH_INTERVAL:
            logger.debug("id=%s file chunk=%s total_size=%s" % ( dl_info["id"], self._chunks, self._total_size))
            # TODO: proper logging
            Backend.touch(dl_info["id"])

    def file_exists_and_is_valid(self, local_path, md5sum):
        if not os.path.exists(local_path):
            return False
        else:
            local_md5 = common.generate_md5(local_path, base_64=True)
            return local_md5 == md5sum

    def make_local_path(self, dl_info):
        # path = os.path.join(self.output_dir, dl_info["download_file"]["destination"])
        path = self.output_dir + dl_info["download_file"]["destination"]
        return path

    def reset(self):
        self._chunks = 0
        self._total_size = 0
        return


class Backend:

    @classmethod
    def next(cls, account, project=None, location=None, number=1):
        """
        """
        path = "downloader/next"
        params = {"account": account} #, "project": project, "location": location}
        return Backend.get(path, params)

    @classmethod
    def touch(cls, id, bytes_transferred=0):
        path = "downloader/touch/%s" % id
        kwargs = {"bytes_transferred": bytes_transferred}
        return Backend.put(path, kwargs)

    @classmethod
    def finish(cls, id, bytes_downloaded=0):
        path = "downloader/finish/%s" % id
        if bytes_downloaded == None:
            payload = {}
        else:
            payload = {"bytes_downloaded": bytes_downloaded}
        return Backend.put(path, payload)

    @classmethod
    def fail(cls, id, bytes_downloaded=0):
        path = "downloader/fail/%s" % id
        if bytes_downloaded == None:
            payload = {}
        else:
            payload = {"bytes_downloaded": bytes_downloaded}
        return Backend.put(path, payload)

    @classmethod
    def get(cls, path, params):
        url = cls.make_url(path)
        headers = cls.make_headers()
        result = requests.get(url, params=params, headers=headers)
        try:
            return result.json()
        except:
            tb = traceback.format_exc()
            print tb
            error = sys.exc_info()[0]
            print error
            return []


    @classmethod
    def put(cls, path, data):
        url = cls.make_url(path)
        headers = cls.make_headers()
        result = requests.put(url, headers=headers, data=data)
        return result.json()

    @classmethod
    def post(cls, path, data):
        url = cls.make_url(path)
        headers = cls.make_headers()
        result = requests.post(url, headers=headers, data=data)
        return result.json()

    @staticmethod
    def make_url(path):
        # url_base = "104.196.62.220"
        url_base = "104.198.192.129"
        # url_base = "127.0.0.1:8080"
        return "http://%s/api/%s" % (url_base, path)

    @staticmethod
    def make_headers():
        token = CONFIG.get("conductor_token")
        return {
            "accept-version": "v1",
            "authorization": "Token %s" % token
        }


class Downloader(object):
    """
    Downloader control object

    This class maintains the process worker "pool" and the shared state object.
    """

    def __init__(self, args):
        self.__dict__.update(args)
        self.output_dir = self.output or ""
        self._workers = []
        self._run_state = multiprocessing.Array('c', "stoppingorstuff")
        self._run_state.value = "running"
        signal.signal(signal.SIGINT, self.sig_handler)

    def run(self):
        self.start_daemon()

    def start_daemon(self):
        """
        Initialize the process 'pool'.
        """
        print "starting daemon"
        self.init_workers()
        [wrk.start() for wrk in self._workers]

    def state(self):
        "return the shared state objects value"
        return self._run_state.value

    def stop(self):
        "tell all workers to stop what they're doing and clean up"
        self._mod_state("stopping")

    def shutdown(self):
        "tell all workers to stop processing new files while completing any current work"
        self._mod_state("shutting_down")

    def _mod_state(self, state):
        self._run_state.value = state

    def init_workers(self):
        "initialize workers with shared state object"
        self._workers = [DownloadWorker(self._run_state,
                                        CONFIG.get("account"),
                                        output_dir=getattr(self, "output", ""),
                                        project=getattr(self, "project", None),
                                        location=getattr(self, "location", None)) for i in range(self.thread_count)]

    def sig_handler(self, sig, frm):
        print "ctrl-c exit..."
        self.stop()
        sys.exit(0)


def run_downloader(args):
    '''
    '''
    # convert the Namespace object to a dictionary
    args_dict = vars(args)

    # Set up logging
    log_level_name = args_dict.get("log_level") or CONFIG.get("log_level")
    log_level = loggeria.LEVEL_MAP.get(log_level_name)
    logger.debug('Downloader parsed_args is %s', args_dict)
    log_dirpath = args_dict.get("log_dir") or CONFIG.get("log_dir")
    set_logging(log_level, log_dirpath)
    if not args_dict["thread_count"]:
        args_dict["thread_count"] = 5

    d = Downloader(args_dict)
    d.run()
    return


def set_logging(level=None, log_dirpath=None):
    log_filepath = None
    if log_dirpath:
        log_filepath = os.path.join(log_dirpath, "conductor_dl_log")
    loggeria.setup_conductor_logging(logger_level=level,
                                     console_formatter=LOG_FORMATTER,
                                     file_formatter=LOG_FORMATTER,
                                     log_filepath=log_filepath)
