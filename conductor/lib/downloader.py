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
import multiprocessing
import requests

NEXT_DL_URL = ""
WORKER_POOL_SIZE = 2
WORKER_PAUSE_DURATION = 15
DOWNLOAD_CHUNK_SIZE = 2048


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
    def __init__(self, run_state):
        """
        Initialize download worker process.

        """
        super(DownloadWorker, self).__init__()
        self._run_state = run_state
        self._chunks = 0
        self._total_size = 0

    def run(self):
        "called at Instance.start()"
        print "worker start %s" % self.name
        while self._run_state.value == "running":
            next_dl = self.get_next_download()
            if next_dl:
                self.download_file(next_dl)
            else:
                self.wait()
        return

    def get_next_download(self):
        "fetch the next downloadable file, return siugned url."
        result = Backend.next(self.account)[0]
        return result

    def wait(self):
        "pause between empty get_next_download() calls"
        time.sleep(WORKER_PAUSE_DURATION)

    def download_file(self, dl_info):
        "stream a file to disk, report progress to server periodically."
        # TODO: check existing file/hash
        # TODO: retry mechanism
        url = dl_info["url"]
        local_file = self.make_local_path(dl_info)
        req = requests.get(url, stream=True)
        try:
            with open(local_file, 'wb') as f:
                for chunk in req.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    if self._run_state.value != "stopping":
                        if chunk:
                            f.write(chunk)
                            self._chunks += 1
                            self._total_size += sys.getsizeof(chunk)
                            if not self._chunks % 1000:
                                print "proc: %s  file chunks -> %s  total_size: %s" % ( self.name, self._chunks, self._total_size )
                                # TODO: proper logging
                                Backend.touch(dl_info["id"])
                    else:
                        print "quit!"
                        # TODO: cancel/stop event cleanup, if any
                        return
        except:
            error = sys.exc_info()[0]
            print error
            # TODO: proper logging
            # TODO: cancel/stop event cleanup, if any
            return
        else:
            # TODO: validate md5, retry etc
            Backend.finish(dl_info["id"])
            return local_file

    def make_local_path(self, dl_info):
        # TODO: mod with passed in local root
        path = dl_info["download_file"]["destination"]
        return path


class Backend:

    @classmethod
    def next(cls, account, project=None, location=None, number=1):
        """
        Sample result:

        [
            {
                "bytes_transferred": 0,
                "download_file": {
                    "account": "foo",
                    "destination": "/tmp/cental/cental.001.exr",
                    "dlid": "2000001",
                    "id": 2,
                    "jid": "12345",
                    "location": "location",
                    "md5": "p1vB6LLIQIoJDvDtjqJocQ==",
                    "priority": 1,
                    "project": null,
                    "source_file": "cental/cental.001.exr",
                    "status": "in-progress",
                    "tid": "001"
                },
                "id": 2,
                "inserted_at": "2016-10-03T22:30:31",
                "url": "https://storage.googleapis.com/moon-walk-1/accounts/foo/hashstore/p1vB6LLIQIoJDvDtjqJocQ==?Expires=1478115003&GoogleAccessId=moon-walk-1%40appspot.gserviceaccount.com&Signature=lSJxTsRPLw0KqjDJLDQq526wJEr5surD1rqWy8ZiWWChroITtX8Tq1FBFJS41wmDNglviw8N7Q7k9eC6clLWHCh9fDs8nJHVcUloBvnirCsPkBwUqTY%2FyR2Du7MgQ6XkLfp3JQnO12orSFKLf9TDSyZbjyKIst5I0AQsdapxeavhRp3ZxyQpaWrOLgaZ%2BRHkrrwMJGaAOweRlzWuoOWqGHWIYrvaI7FRmjpUnSNAkQNY58KDO%2Far2TEtOGRob9SNfsysH%2BuSWOvYRgxEbtjDkq11hAlofSnHiWO4qRHdoyLyxLz5rXJXeBy%2FMSpv8tDN5WBNI9wCDSXX%2FAHRTb%2BBwA%3D%3D"
            }
        ]
        """
        path = "downloader/next"
        params = {"account": account, "project": project, "location": location}
        return get(cls, path, params)

    @classmethod
    def touch(cls, id, bytes_transferred=0):
        path = "downloader/touch/%s" % id
        kwargs = {"bytes_transferred": bytes_transferred}
        return put(cls, path, kwargs)

    @classmethod
    def finish(cls, id):
        path = "downloader/finish/%s" % id
        return put(cls, path, {})
        return

    @classmethod
    def get(cls, path, params):
        url = cls.make_url(path)
        headers = cls.make_headers()
        result = requests.get(url, params=params, headers=headers)
        return result.json

    @classmethod
    def put(cls, path, data):
        url = cls.make_url(path)
        headers = cls.make_headers()
        result = requests.put(url, headers=headers, data=data)
        return result.json

    @classmethod
    def post(cls, path, data):
        url = cls.make_url(path)
        headers = cls.make_headers()
        result = requests.post(url, headers=headers, data=data)
        return result.json

    @staticmethod
    def make_url(path):
        url_base = "104.196.62.220"
        return "http://%s/api/%s" % (url_base, path)

    @staticmethod
    def make_headers():
        token = CONFIG.get("conductor_token")
        return {
            "accept-version": "v1",
            "authorization": token
        }


class Downloader(object):
    """
    Downloader control object

    This class maintains the process worker "pool" and the shared state object.
    """

    def __init__(self, args):
        self.__dict__.update(args)
        self._workers = []
        self._run_state = multiprocessing.Value('c', "running")
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
        self._workers = [DownloadWorker(self._run_state) for i in range(self.thread_count)]

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
