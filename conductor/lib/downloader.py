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
        # TODO: replace psuedo-code when service is up
        # req = requests.get(NEXT_DL_URL)
        # result = req.body
        # return result
        return "http://download.thinkbroadband.com/1GB.zip"

    def wait(self):
        "pause between empty get_next_download() calls"
        time.sleep(WORKER_PAUSE_DURATION)

    def download_file(self, dl_info):
        "stream a file to disk, report progress to server periodically."
        # TODO: check existing file/hash
        # TODO: retry mechanism
        url = dl_info
        # TODO: make rel local path
        local_file = "/tmp/1gb-%s.zip" % time.time()
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
                                # TODO: call /downloader/touch/:id
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
            # TODO: call /downloader/finish/:id
            return local_file

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

    def main(self):
        if getattr(self, "job_ids", None):
            print "use downloader2"
        elif getattr(self, "task_id", None):
            print "use downloader2"
        else:
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
        self._workers = [DownloadWorker(self._run_state) for i in range(WORKER_POOL_SIZE)]

    def sig_handler(self, sig, frm):
        print "ctrl-c exit..."
        self.stop()
        sys.exit(0)
