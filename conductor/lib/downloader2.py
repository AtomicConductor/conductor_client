#!/usr/bin/env python

""" Command Line Process to run downloads.
"""

import argparse
import base64
import collections
import datetime
import errno
import functools
import imp
import json
import os
import Queue
import logging
import logging.handlers
import multiprocessing
import ntpath
import re
import requests
import random
import shutil
import sys
import tempfile
import time
import threading
import traceback
import urllib2
import hashlib


try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from conductor import CONFIG
from conductor.lib import common, api_client, loggeria

BYTES_1KB = 1024
BYTES_1MB = BYTES_1KB ** 2
BYTES_1GB = BYTES_1KB ** 3


CHUNK_SIZE = 1024

CONNECTION_EXCEPTIONS = (requests.exceptions.SSLError,
                         urllib2.HTTPError,
                         urllib2.URLError)

LOG_FORMATTER = logging.Formatter('%(asctime)s  %(name)s%(levelname)9s  %(threadName)s:  %(message)s')

logger = logging.getLogger(__name__)


def dec_retry(retry_exceptions=Exception, tries=8, static_sleep=None):
    '''
    DECORATOR
    
    Retry calling the decorated function using an exponential backoff.

    retry_exceptions: An Exception class (or a tuple of Exception classes) that
                    this decorator will catch/retry.  All other exceptions that
                    occur will NOT be retried. By default, all exceptions are
                    caught (due to the default arguemnt of Exception)

    tries: int. number of times to try (not retry) before raising
    static_sleep: The amount of seconds to sleep before retrying. When set to 
                  None, the sleep time will use exponential backoff. See below.  

    This retry function not only incorporates exponential backoff, but also
    "jitter".  see http://www.awsarchitectureblog.com/2015/03/backoff.html.
    Instead of merely increasing the backoff time exponentially (determininstically),
    there is a randomness added that will set the sleeptime anywhere between
    0 and the full exponential backoff time length.

    '''
    def retry_decorator(f):

        @functools.wraps(f)
        def retry_(*args, **kwargs):
            for try_num in range(1, tries + 1):
                try:
                    return f(*args, **kwargs)
                except retry_exceptions, e:
                    if static_sleep != None:
                        sleep_time = static_sleep
                    else:
                        # use random for jitter.
                        sleep_time = random.randrange(0, 2 ** try_num)
                    msg = "%s, Retrying in %d seconds..." % (str(e), sleep_time)
                    logger.warning(msg)
                    time.sleep(sleep_time)
            return f(*args, **kwargs)
        return retry_
    return retry_decorator


def random_exeption(percentage_chance):
    if random.random() < percentage_chance:
        raise Exception("Random exception raised (%s percent chance)" % percentage_chance)
    logger.debug("Skipped random exception (%s chance)", percentage_chance)

def dec_random_exception(percentage_chance):
    '''
    DECORATOR for creating random exceptions for the wrapped function.
    This is used for simluating errors to test downloader recovery behavior/robustness
    '''
    def catch_decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwds):
            random_exeption(percentage_chance)
            return func(*args, **kwds)
        return wrapper
    return catch_decorator



class ThreadState(object):
    '''
    Use a class as mutable datatype so that it can be used across threads
    '''
    pass


class FileDownloadState(ThreadState):
    STATE_QUEUED = "QUEUED"
    STATE_PREPARING_DIRECTORY = "PREPARING DIRECTORY"
    STATE_HASHING_EXISTING_FILE = "HASHING EXISTING FILE"
    STATE_DOWNLOADING = "DOWNLOADING"
    STATE_COMPLETE = "COMPLETE"




    bytes_downloaded = 0
    hash_progress = 0
    status = STATE_QUEUED
    use_existing = False
    filepath = None
    time_started = None
    time_completed = None
    file_info = None
    thread_name = ""
    download_id = ""

    def get_duration(self):
        '''
        Return the amount of time in seconds
        '''
        if self.time_started:
            if self.time_completed:
                return self.time_completed - self.time_started
            else:
                return time.time() - self.time_started

        return 0



class TablePrinter(object):
    '''
    ############## DOWNLOAD HISTORY #################
    COMPLETED AT         DOWNLOAD ID       JOB    TASK       SIZE  ACTION  DURATION  THREAD     FILEPATH
    2016-01-16 01:12:46  5228833175240704  00208  010    137.51MB  DL      0:00:57   Thread-12  /tmp/conductor_daemon_dl/04/cental/cental.010.exr
    2016-01-16 01:12:42  6032237141164032  00208  004    145.48MB  DL      0:02:24   Thread-2   /tmp/conductor_daemon_dl/04/cental/cental.004.exr
    2016-01-16 01:12:40  5273802288136192  00208  012    140.86MB  DL      0:02:02   Thread-16  /tmp/conductor_daemon_dl/04/cental/cental.012.exr

    '''

    # The columns of data to show (and the order in which they are shown)
    column_names = []

    # The title of the table
    title = ""

    # A list of dictionaries, each dict represents a row, where the key is the column name, and the value is the...value
    data = []

    # A dict which contains callable functions that can be used to condition each column entry of the table
    modifiers = {}

    # The characters to print between the columns (to seperate them)
    column_spacer = "  "

    row_spacer = "\n"

    upper_header = False

    def __init__(self, data):
        self.data = data

    def make_table_str(self):
        title = self.get_title()
        header = self.get_table_header()

        rows = [title, header]
        for row_dict in self.data:
            rows.append(self.make_row_str(row_dict))
        return self.row_spacer.join(rows)


    def make_row_str(self, row_dict):
        column_values = []
        for column_name in self.column_names:
            column_value = self.make_column_str(column_name, row_dict)
            column_values.append(column_value)
        return self.column_spacer.join(column_values)


    def make_column_str(self, column_name, row_dict):
        column_data = str(row_dict.get(column_name, ""))
        return self.modify_data(column_name, column_data)


    def modify_data(self, column_name, column_data):

        modifier = self.modifiers.get(column_name)
        if modifier:
            func, args = modifier
            column_data = func(column_data, *args)
        return  column_data


    def get_title(self):
        return self.title

    def get_table_header(self):
        column_names = []
        for column_name in self.column_names:
            mod_column_name = self.modify_data(column_name, column_name)
            mod_column_name = mod_column_name.upper() if self.upper_header else mod_column_name
            column_names.append(mod_column_name)

        return self.column_spacer.join(column_names)

class HistoryTablePrinter(TablePrinter):


    title = "############## DOWNLOAD HISTORY #################"

    column_names = ["Completed at", "Download ID", "Job", "Task", "Size", "Action", "Duration", "Thread", "Filepath"]

    modifiers = {

                 "Completed at": (str.ljust, (19,)),
                 "Download ID": (str.ljust, (16,)),
                 "Job": (str.ljust, (5,)),
                 "Task": (str.ljust, (4,)),
                 "Size": (str.rjust, (9,)),
                 "Action": (str.ljust, (6,)),
                 "Duration": (str.ljust, (8,)),
                 "Thread": (str.ljust, (9,))}


    upper_header = True


class TaskDownloadState(ThreadState):


    STATE_QUEUED = "QUEUED"
    STATE_PREPARING_DIRECTORY = "PREPARING DIRECTORY"
    STATE_HASHING_EXISTING_FILE = "HASHING EXISTING FILE"
    STATE_DOWNLOADING = "DOWNLOADING"
    STATE_COMPLETE = "COMPLETE"
    STATE_ERROR = "ERROR"

    ENTITY_STATES = {STATE_QUEUED:"downloading",
                      STATE_PREPARING_DIRECTORY: "downloading",
                      STATE_HASHING_EXISTING_FILE: "downloading",
                      STATE_DOWNLOADING: "downloading",
                      STATE_COMPLETE: "downloaded",
                      STATE_ERROR: "pending"}



    def __init__(self):
        self.reset()


    def get_bytes_downloaded(self):
        bytes_list = [file_state.bytes_downloaded for file_state in self.file_download_states]
        return sum(bytes_list or [0])

    def reset_bytes_downloaded(self):
        for file_state in self.file_download_states:
            file_state.bytes_downloaded = 0

    def get_duration(self):
        '''
        Return the amount of time in seconds
        '''
        if self.time_started:
            if self.time_completed:
                return self.time_completed - self.time_started
            else:
                return time.time() - self.time_started

        return 0

    def get_entity_status(self):
        '''
        Return corresponding entity status for the TaskDownloadState's current status
        '''
        return self.ENTITY_STATES[self.status]


    def initialize(self, task_download):
        '''
        Reset/initialize the properties
        '''
        self.reset()
        self.task_download = task_download

    def reset(self):
        self.status = self.STATE_QUEUED
        self.task_download = {}
        self.file_download_states = {}
        self.time_started = None
        self.time_completed = None



class Downloader(object):
    '''
    A Downloader daemon which downloads completed frames from finished tasks. 
    
    
    Each task has an associated Download entitity that represents
    all images/files that were produced from that task. A task may have more than
    file to download.
    
    1. Query the app for the "next" download to download.  The app will return
       the Download that it deems most appropriate (probably of the lowest jobid).
       Note the app will automatically change the status of that Download entity
       to "downloading".  This is probably a terrible model (but it's what I'm
       inheriting).  Note that there is cron job that resets Download entities
       that are in state of Downloading but have not "dialed home" after x amount
       of time.
       
   2. Place this Download in the queue to be downloaded. 
   
   3. Spawn threads to actively take "work" (Downloads) from the queue.
   
   4. Each thread is responsible for downloading the Download that it took from
      the queue.
      
  5. Each thread is responsible for updating the app of it's downloading status:
      "downloading", etc
      
  6. Each thread is responsible for catching their own exceptions and placing the
     Download back into the queue
     
  7. 
    
    Because the downloader is threaded, it makes communication/tracking of data
    more difficult.  In order to faciliate this, ThreadState objects are shared
    across threads to read/write data to. This allows download progress to
    be communicated from multiple threads into a single object, which can tehn 
    be read from a single process and "summarized".
 
    A TaskDownloadState
       .files= [FileDownloadState, FileDownloadState]
    
    
    To complicate matters further, if the downloader is killed (via keyboard, etc),
    the it should clean up after itself.  So we need to catch the
    SIGINT EXIT signal at any point in the code and handle it gracefully.  
    
    '''

    # The amount of time to "sleep" before querying the app for more downloads
    naptime = 15
    endpoint_downloads_next = '/downloads/next'
    endpoint_downloads_job = '/downloads/%s'
    endpoint_downloads_status = '/downloads/status'


    download_progess_polling = 2
    md5_progess_polling = 2

    history_queue_max = 100
    start_time = None

    # Record last download history
    _download_history = None

    # record the original threads that started
    _original_threads = ()

    # record last threads alive
    _threads_alive = ()


    def __init__(self, thread_count=None, location=None, output_dir=None):



        # Turn on the SIGINT handler.  This will catch
        common.register_sigint_signal_handler()

        self.api_client = api_client.ApiClient()

        self.thread_count = int(thread_count or CONFIG['thread_count'])
        logger.debug("thread_count: %s", self.thread_count)

        self.location = location or CONFIG.get("location")
        logger.debug("location: %s", self.location)

        self.output_dir = output_dir

    @classmethod
    def start_daemon(cls, thread_count=None, location=None, output_dir=None, summary_interval=10):
        '''
        Run the downloader as a daemon
        '''
        downloader = cls(thread_count=thread_count, location=location, output_dir=output_dir)
        thread_states = downloader.start(summary_interval=summary_interval)
        while not common.SIGINT_EXIT:
            pass
#             sleep_time = 5
#             logger.debug("sleeping1: %s", sleep_time)
#             time.sleep(sleep_time)
        downloader._print_download_history()
        downloader.print_uptime()


    @classmethod
    def download_jobs(cls, job_ids, task_id=None, thread_count=None, output_dir=None):
        '''
        Run the downloader for explicit jobs, and terminate afterwards.
        '''
        downloader = cls(thread_count=thread_count, output_dir=output_dir)
        thread_states = downloader.start(job_ids, task_id=task_id)
        while not common.SIGINT_EXIT and (not downloader.pending_queue.empty() or not downloader.downloading_queue.empty()):
            sleep_time = 2
#             logger.debug("sleeping2: %s", sleep_time)
            time.sleep(sleep_time)

        downloader._print_download_history()
        downloader.print_uptime()


    def start(self, job_ids=None, task_id=None, summary_interval=10):
        # Create new queues
        self.start_time = time.time()
        self.pending_queue = Queue.Queue()
        self.downloading_queue = Queue.Queue()
        self.history_queue = Queue.Queue()

        # If a job id has been specified then only load the queue up with that work
        if job_ids:
            self.history_queue_max = None
            self.get_jobs_downloads(job_ids, task_id)

        # otherwise create a queue thread the polls the app for wor
        else:
            self.start_queue_thread()


        task_download_states = self.start_download_threads(self.downloading_queue, self.pending_queue)
        thread_states = {"task_downloads":task_download_states}


        self.start_summary_thread(thread_states, interval=summary_interval)

        # Record all of the original threads immediately so that we can monitor their state change
        self._original_threads = threading.enumerate()
        return thread_states

    def print_uptime(self):
        '''
        Return the amount of time that the uploader has been running, e.g "0:01:28"
        '''
        seconds = time.time() - self.start_time
        human_duration = get_human_duration(seconds)
        logger.info("Uptime: %s", human_duration)



    def start_queue_thread(self):
        '''
        Start and return a thread that is responsible for pinging the app for
        Downloads to download (and populating the queue)
        '''

        thread = threading.Thread(name="QueueThread",
                                  target=self.queue_target,
                                   args=(self.pending_queue, self.downloading_queue))
        thread.setDaemon(True)
        thread.start()
        return thread

    def start_summary_thread(self, thread_states, interval):
        '''
        Start and return a thread that is responsible for pinging the app for
        Downloads to download (and populating the queue)
        '''
        # logger.debug("thread_states: %s", thread_states)
        thread = threading.Thread(name="SummaryThread",
                                  target=self.print_summary,
                                   args=(thread_states, interval))
        thread.setDaemon(True)
        thread.start()
        return thread

    def start_download_threads(self, downloading_queue, pending_queue):
        threads = []

        task_download_states = []

        for thread_number in range(self.thread_count):

            # create a task download state. This object is persistant and resused over and over again for each Task that a thread downloads
            # It's important that the state information is wiped clean (reset) every time a new task begins.
            task_download_state = TaskDownloadState()
            task_download_states.append(task_download_state)
            thread = threading.Thread(target=self.download_target,
                                      args=(pending_queue, downloading_queue, task_download_state))
            thread.setDaemon(True)
            thread.start()
            threads.append(thread)
        return task_download_states


    def start_reporter_thread(self, download_data):
        reporter_thread_name = "ReporterThread"
        current_thread_name = threading.current_thread().name
        thread_number_match = re.match("Thread-(\d+)", current_thread_name)
        if thread_number_match:
            reporter_thread_name += "-%s" % thread_number_match.groups()[0]

        thread = threading.Thread(name=reporter_thread_name,
                                  target=self.reporter_target,
                                   args=(download_data, threading.current_thread()))
        thread.setDaemon(True)
        thread.start()
        return thread

    def queue_target(self, pending_queue, downloading_queue):
        '''
        Fill the download queue by quering the app for the "next" Download. 
        Only fill the queue to have as many items as there are threads. 
        
        Perpetually run this this function until the daemon has been terminated
        '''


        while True:

            try:

                empty_queue_slots = (self.thread_count * 2) - pending_queue.qsize()
                # If the queue is full, then sleep
                if empty_queue_slots <= 0:
    #                 logger.debug('Pending download queue is full (%s Downloads). Not adding any more Downloads' % self.thread_count)
    #                 sleep_time = 0.5
    #                 logger.debug("sleeping3: %s", sleep_time)
    #                 time.sleep(sleep_time)
                    continue

                logger.debug("empty_queue_slots: %s", empty_queue_slots)



                # Get the the next download
                max_count = 20  # Cap the request to 20 Downloads at a time (this keeps the request from not taking a super long time). This is an arbitrary number and can be adjusted as needed
                downloads = self.get_next_downloads(count=min([empty_queue_slots, max_count]))
    #             logger.debug('download: %s', download)

                # If there is not a download, then sleep
                if not downloads:
                    logger.debug('No more downloads to queue. sleeping %s seconds...', self.naptime)
                    self.nap()
                    continue

                # Ensure that each Download is not already in the pending/downloading queues
                for download in downloads:
                    if _in_queue(pending_queue, download, "download_id") or  _in_queue(downloading_queue, download, "download_id"):
                        logger.warning("Omitting Redundant Download: %s", download)
                        continue

                    # Add the download to the pending queue
                    logger.debug("adding to pending queue: %s", download)
                    self.pending_queue.put(download)
            except:
                logger.exception("Exception occurred in QueueThead:\n")
                self.nap()

    def nap(self):
        while not common.SIGINT_EXIT:
#             print "Sleeping4 for %s" % self.naptime
            time.sleep(self.naptime)
            return


    @common.dec_timer_exit
    def get_next_downloads(self, count):
        try:
            downloads = _get_next_downloads(self.location, self.endpoint_downloads_next, self.api_client, count=count)
            return downloads
        except Exception as e:
            logger.exception('Could not get next download')


    def get_jobs_downloads(self, job_ids, task_id):

        for job_id in job_ids:
            endpoint = self.endpoint_downloads_job % job_id
            downloads = _get_job_download(endpoint, self.api_client, job_id, task_id)
            if downloads:
                for task_download in downloads.get("downloads", []):
                    print "putting in queue: %s" % task_download
                    self.pending_queue.put(task_download, block=True)





    @common.dec_catch_exception(raise_=True)
    def download_target(self, pending_queue, downloading_queue, task_download_state):
        '''
        This function is called in a new thread (and many threads may be 
        executing this at a single time). This function is responsible for
        downloading a single Download (essentially an entity in Datastore which
        represents the output data from a single Task).  This may consist of many
        files.  
        
        This function pulls one Download from the pending queue and attempts
        to download it.  If it fails, it places it back on the queue. 
        
        The function also spawns a child thread that is responsible for constantly
        updating the app with the status of the Download, such as:
            - status (e.g. "pending", "downloading", "downloaded")
            - bytes transferred (the total amout of bytes that have been transferred
              for the Download. Note that these bytes encompass all of the bytes
              that have been transferred for ALL of the files that are part
              of the Download (as opposed to only a single file) 
        
        
        task_download_state: a class, serving as global mutable object, which allows
                        this thread to report data about its Download state,
                        so that other threads can read and output that data.
                        This object is persistant for each thread, and is used
                        over and over again, everytime thime this  function is called, 
                        for each Task that a thread downloads
                        It's important that the state information is wiped clean (reset) every time a new task begins.
                        This is the resposnbility of this function
                
        '''
        task_download_state.thread_name = threading.currentThread().name

        # Start the reporter sub thread (feeding it empty data)
        # Setup the reporter child thread to update the apps' Download entity
        self.start_reporter_thread(task_download_state)

        while not common.SIGINT_EXIT:
            task_download = None

            try:
                # Get the next task download from the pending queue.
                task_download = pending_queue.get(block=True)

                # Tell the pending queue that the task has been completed (to remove the task from the queue)
                pending_queue.task_done()

                # Transfer the task download into the downloading queue
                downloading_queue.put(task_download)

                logger.debug('download: %s', task_download)

                # The task_download_state variable is constructed as a mutable object (a class)
                # so that it can be passed into multiple functions/threads and have
                # them read/write to it like a global variable.
                # Initialize/reset the task_download_state
                task_download_state.initialize(task_download)
                task_download_state.status = TaskDownloadState.STATE_DOWNLOADING

                # Explicity report the Download status (to indicate that it's now "downloading"
                self.report_download_status(task_download_state)

                output_dir = task_download['output_dir']
                logger.info("output directory: %s", output_dir)

                if self.output_dir:
                    output_dir = self.output_dir
                    logger.info("Overriding default output directory: %s", output_dir)


                for file_info in task_download['files']:
#                     logger.debug("file_info: %s", file_info)

                    # Create file state object
                    file_download_state = FileDownloadState()
                    file_download_state.file_info = file_info
                    file_download_state.thread_name = threading.currentThread().name
                    file_download_state.download_id = task_download["download_id"]

                    # attach the file state object to the task state object
                    task_download_state.file_download_states[file_download_state] = file_info

                    # Define the local filepath to download to
                    local_filepath = os.path.join(output_dir, file_info["relative_path"])

                    # Record the filepath to the state object
                    file_download_state.filepath = local_filepath

                    logger.debug('Handling task file: %s', local_filepath)

                    # Get the immediate parent directory for the file to be downloaded.
                    # Note that this is not necessarily the same as the output_dir.
                    # The output_dir is simply the top level directory to transer
                    # the files to. It does not necessarily account for a render's
                    # generated subdirectories
                    dirpath = os.path.dirname(local_filepath)

                    # Ensure that the destination directory exists and set open permissions
                    logger.debug("Creating destination directory if necessary: %s", dirpath)
                    file_download_state.status = FileDownloadState.STATE_PREPARING_DIRECTORY
                    safe_mkdirs(dirpath)

                    logger.debug("chmodding directory: %s", dirpath)
                    try:
                        chmod(dirpath, 0777)
                    except:
                        logger.warning("Failed to chmod filepath  %s", dirpath)


                    file_download_state.time_started = time.time()
                    self.download_file(file_info['url'],
                                       local_filepath,
                                       file_info['md5'],
                                       file_download_state)

                    file_download_state.status = FileDownloadState.STATE_COMPLETE
                    file_download_state.time_completed = time.time()
                    self.add_to_history(file_download_state)

                # Update the status downloaded
                task_download_state.status = TaskDownloadState.STATE_COMPLETE
                # Remove theDownload from the downloading queue.
                downloading_queue.get(block=False)
                downloading_queue.task_done()


            except:
                if task_download:
                    task_download_state.reset_bytes_downloaded()
                    task_download_state.status = TaskDownloadState.STATE_ERROR
                    logger.exception("Failed to download Download %s", task_download.get('download_id'))
                    logger.debug("Putting Download back on queue: %s", task_download)
                    pending_queue.put(task_download)

            # Explicity call report_download_status to tell the app the status
            # of the Download.  We can't always rely on the reporter in the
            # thread because it only pings the app every x seconds.

            # Make sure this doesn't throw an exception. Don't want to kill the thread.
            try:
                self.report_download_status(task_download_state)
            except:
                # I think the worst that could happen is that the Download
                # may not get it's status changed to "downloaded".  This will
                # eventually get cleaned up by the cron, and prompt a redownloading
                download_id = task_download_state.task_download.get("download_id")
                logger.exception("Failed to report final status for Download %s, due to error", download_id)

            # Reset The task_download_state object
            task_download_state.reset()



        # IF the daemont is terminated, clean up the active Download, resetting
        # it's status on the app
        logger.debug("Exiting thread. Cleaning up state for Download: ")
        task_download_state.reset_bytes_downloaded()
        task_download_state.status = TaskDownloadState.STATE_ERROR
        self.report_download_status(task_download_state)
        downloading_queue.get(block=True)
        downloading_queue.task_done()



    def reporter_target(self, task_download_state, downloader_thread):

        while True:

            try:
    #             logger.debug("threading.threading.currentThread(): %s", threading.currentThread())
    #             logger.debug('bytes_downloaded is %s' % bytes_downloaded)
    #             logger.debug('done is %s' % done)

                if common.SIGINT_EXIT:
                    task_download_state.status = TaskDownloadState.STATE_ERROR
                    task_download_state.reset_bytes_downloaded()

                if task_download_state.task_download != None:
                    bytes_downloaded = task_download_state.get_bytes_downloaded()
                    response_string, response_code = self.report_download_status(task_download_state)
            except:
                logger.exception("failed to report download status")

#                 logger.debug("updated status: %s\n%s", response_code, response_string)
#
#             if task_download_state.status != "downloaded" and not common.SIGINT_EXIT:

            sleep_time = 5
            # logger.debug("sleeping6: %s", sleep_time)
            time.sleep(sleep_time)

            # Check to make sure that that the downloader thread that this reporter thread
            # is reporting about is still alive. Otherwise exit the reporter loop
            if not downloader_thread.is_alive():
                logger.warning("Detected %s thread is dead. Exiting %s thread now",
                             downloader_thread.name, threading.current_thread().name)
                return

#     @dec_random_exception(percentage_chance=0.05)
    @dec_retry(tries=3, static_sleep=1)
    def download_file(self, url, local_filepath, md5, file_state):
        '''
        For the given file information, download the file to disk.  Check whether
        the file already exists and matches the expected md5 before downloading.
        '''
        # Reset bytes downloaded to 0 (in case of retries)
        file_state.bytes_downloaded = 0

        logger.debug('Checking for existing file %s', local_filepath)

        # If the file already exists on disk
        if os.path.isfile(local_filepath):
            file_state.status = FileDownloadState.STATE_HASHING_EXISTING_FILE
            local_md5 = common.generate_md5(local_filepath, base_64=True, poll_seconds=self.md5_progess_polling, state=file_state)
            # If the local md5 matchs the expected md5 then no need to download. Skip to next file
            if md5 == local_md5:
                file_state.use_existing = True
                logger.info('Existing file is up to date: %s', local_filepath)
                return

            logger.debug('md5 does not match existing file: %s vs %s', md5, local_md5)

            logger.debug('Deleting dirty file: %s', local_filepath)
            delete_file(local_filepath)

        file_state.status = FileDownloadState.STATE_DOWNLOADING

        # Download to a temporary file and then move it
        dirpath, filename = os.path.split(local_filepath)
        # hack to use tempfile to generate a unique filename.  close file object immediately.  This will get thrown out soon
        tmpfile = tempfile.NamedTemporaryFile(prefix=filename, dir=dirpath)
        tmpfile.close()  # close this. otherwise we get warnings/errors about the file handler not being closed
        tmp_filepath = tmpfile.name
        logger.debug("tmp_filepath: %s", tmp_filepath)
        # download the file.
        new_md5 = download_file(url, tmp_filepath, poll_rate=self.download_progess_polling, state=file_state)

        logger.debug("new_md5: %s", new_md5)
        if new_md5 != md5:
            try:
                logger.debug("Cleaning up temp file: %s", tmp_filepath)
                os.remove(tmp_filepath)
            except:
                logger.warning("Could not cleanup temp file: %s", tmp_filepath)
            raise Exception("Downloaded file does not have expected md5. %s vs %s: %s" % (new_md5, md5, tmp_filepath))

        logger.debug("File md5 verified: %s", tmp_filepath)

        logger.debug("Moving: %s to %s", tmp_filepath, local_filepath)
        shutil.move(tmp_filepath, local_filepath)

        # Set file permissions
        logger.debug('\tsetting file perms to 666')
        chmod(local_filepath, 0666)


#     @dec_random_exception(percentage_chance=0.05)
    def add_to_history(self, file_download_state):

        self.history_queue.put(file_download_state, block=False)

        if self.history_queue_max != None:
            # Only save the last n file downloads
            while self.history_queue.qsize() > self.history_queue_max:
                self.history_queue.get(block=False)


#     @dec_random_exception(percentage_chance=0.05)
    @dec_retry(retry_exceptions=CONNECTION_EXCEPTIONS)
    def report_download_status(self, task_download_state):
        download_id = task_download_state.task_download.get("download_id")
        if not download_id:
            return None, None

        data = {'download_id': download_id,
                'status': task_download_state.get_entity_status(),
                'bytes_downloaded': task_download_state.get_bytes_downloaded(),
                'bytes_to_download': task_download_state.task_download.get('size') or 0}

#         logger.debug("data: %s", data)
#         if data["status"] == "downloaded":
#             print "********DOWNLOADED: %s ********************" % download_id
        return  self.api_client.make_request(self.endpoint_downloads_status,
                                                                      data=json.dumps(data))

    def print_summary(self, thread_states, interval):
        '''
        - total threads running
        - thread names
        - total download threads
        
        Last 20 files downloaded
        Last 20 tasks  downloaded
        Last 20 Downlaods  downloaded
        
        Currently downloading jobs
        Currenly downloading files
        Currently downloading Downloads
        
        
        
        ####### SUMMARY #########################
        Active Thread Count: 14
        
        Threads:
              ErrorThread
              MainThread
              MetricStore
              ProgressThread
              ProgressThread
              ProgressThread
              ProgressThread
              ProgressThread
              ProgressThread
              QueueThread
              Thread-1
              Thread-2
              Thread-3
              Thread-4
              Thread-5
              
              
        #### ACTIVE DOWNLOADS #####
        
         Job 08285 Task 004 - 80% (200/234MB)  - Thread-1
             /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/beauty/deep_lidar.deep.0005.exr  HASHING EXISTING FILE     80%    
             /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/data/deep_lidar.deep.0005.exr    DOWLOADING 20%
            
          
              
         Job 08285 Task 003 - 20%  (20/234MB) - Thread-2
             /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01142.exr
             /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01074.exr
            
          
        #### PENDING DOWNLOADS #####
            Job 08285 Task 006
            Job 08285 Task 007
            Job 08285 Task 008
            Job 08285 Task 009
        
          
          
              
        #### HISTORY ####
        
        Last 20 files downloaded:
        
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01142.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01074.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01038.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01111.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01087.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01143.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01095.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01156.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01016.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01039.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01130.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01030.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01015.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01138.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01063.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01006.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01065.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01096.exr
            /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01055.exr
        
        Last 20 tasks downloaded
            Job 08285 Task 004 (Download 3492394234)
            Job 08285 Task 002 (Download 3492394234)
            Job 08285 Task 003 (Download 3492394234) 
            Job 08285 Task 001 (Download 3492394234)
            Job 08285 Task 000 (Download 3492394234)
            Job 08284 Task 065 (Download 3492394234)
            Job 08283 Task 064 (Download 3492394234)
            Job 08283 Task 063 (Download 3492394234)
            Job 08282 Task 032 (Download 3492394234)
            Job 08282 Task 025 (Download 3492394234)
            Job 08282 Task 001 (Download 3492394234)

        ####################



        
        '''

        while True:
            try:
                self._print_threads_alive()
                self._print_download_history()
                self._print_pending_queue()
                self._print_active_downloads(thread_states)
                self._print_dead_thread_warnings()
            except:
                logger.exception("Failed to report Summary")

            time.sleep(interval)

    def _print_threads_alive(self):
        '''
        Print all running thread names
        '''

        thread_names = sorted([thead.name for thead in threading.enumerate()], key=str.lower)
        # Only print the history if it is different from before
        if thread_names != self._threads_alive:
            logger.info('##### THREADS ALIVE #### (%s):\n\t%s', len(thread_names), "\n\t".join(thread_names))
            self._threads_alive = thread_names
        else:
            logger.info('##### THREADS ALIVE #### [No changes] (%s)', len(thread_names))


    def _print_dead_thread_warnings(self):
        dead_threads = set(self._original_threads).difference(set(threading.enumerate()))
        if dead_threads:
            logger.error("#### DEAD THREADS ####   THIS SHOULD NEVER HAPPEN!\n\t%s", "\n\t".join([str(thread) for thread in dead_threads]))


    def _print_download_history(self):
        '''
        Print the history of the last x Downloads.
        '''
        # Print the history
        file_download_history = reversed(list(self.history_queue.queue))
        file_download_history_summary = self.construct_file_downloads_history_summary(file_download_history)

        # Only print the history if it is different from before
        if file_download_history_summary != self._download_history:
            logger.info(file_download_history_summary)
            self._download_history = file_download_history_summary
        else:
            logger.info('##### DOWNLOAD HISTORY ##### [No changes]')

    def _print_active_downloads(self, thread_states):
        '''
        Print all Downloads that are currently active
        '''
        task_download_states = thread_states.get("task_downloads", [])
        active_downloads_summary = self.construct_active_downloads_summary(task_download_states)
        if active_downloads_summary:
            logger.info(active_downloads_summary)
        else:
            logger.info('##### ACTIVE DOWNLOADS ##### [None]')



    def _print_pending_queue(self):
        pending_downloads = [str(item["download_id"]) for item in list(self.pending_queue.queue)]
        if pending_downloads:
            logger.info('##### PENDING QUEUE ###### (%s)\n\tDownload id: %s', self.pending_queue.qsize(), "\n\tDownload id: ".join(pending_downloads))
        else:
            logger.info('##### PENDING QUEUE ###### [None]')


#
#         logger.info('Downloading Queue (Active Downloads) contains %s items', self.downloading_queue.qsize())
#         for item in list(self.downloading_queue.queue):
#             logger.info('\tDownloading: %s', item["download_id"])
#



#
#         logger.debug("TOTAL THREADS: %s", len(active_threads))
#         logger.debug("DOWNLOAD THREADS: %s", len(active_threads))
#
#         logger.debug("Pending Queue: ")
#         logger.debug("Pending Queue: ")
#         logger.debug("Last %s files downloaded ")
#         logger.debug("Last %s Jobs downloaded ")
#         logger.debug("Last %s Downloads downloaded ")



    def construct_active_downloads_summary(self, task_download_states):

        '''
        #### ACTIVE DOWNLOADS #####
        
         Job 08285 Task 004 - 80% (200/234MB)  - Thread-1
             /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/beauty/deep_lidar.deep.0005.exr
             /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/data/deep_lidar.deep.0005.exr
            
          
              
         Job 08285 Task 003 - 20%  (20/234MB) - Thread-2
             /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01142.exr
             /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/deep_lidar/deep_lidar.deep.01074.exr
            
        '''
        header = "##### ACTIVE DOWNLOADS #####"
        content = ""

        for task_download_state in task_download_states:
            if task_download_state.task_download.get("download_id"):
                content += "\n\n%s" % self._contruct_active_download_summary(task_download_state)

        if content:
            return header + content

        return ""


    def _contruct_active_download_summary(self, task_download_state):
        '''
         Job 08285 Task 004 - 80% (200/234MB)  - Thread-1
             /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/beauty/deep_lidar.deep.0005.exr  20MB    DOWNLOADING 20%
             /Volumes/af/show/wash/shots/MJ/MJ_0080/sandbox/jfunk/katana/renders/MJ_0080_light_v001/data/deep_lidar.deep.0005.exr    30MB    HASHING EXISTING FILE 77%        
        '''
        thread_name = task_download_state.thread_name
        jid = task_download_state.task_download.get("job_id")
        tid = task_download_state.task_download.get("task_id")
        task_size = task_download_state.task_download.get("size", 0)

        bytes_downloaded = task_download_state.get_bytes_downloaded()
        progress_percentage = get_progress_percentage(bytes_downloaded, task_size)

        human_bytes_downloaded = get_human_bytes(bytes_downloaded)
        human_size = get_human_bytes(task_size)

        # Get the string length of the largest filepath that the task is download. This will be used for print margin purpise
        max_filepath_length = max([len(file_state.filepath) for file_state in task_download_state.file_download_states]or [0])

        summary = "Job %s Task %s - %s (%s/%s)  - %s" % (jid, tid, progress_percentage, human_bytes_downloaded, human_size, thread_name)
        for file_state in task_download_state.file_download_states:
            file_size_human = get_human_bytes(file_state.file_info['size'])
            if file_state.status == FileDownloadState.STATE_HASHING_EXISTING_FILE:
                progress_percentage = "%s%%" % file_state.hash_progress
            elif file_state.status == FileDownloadState.STATE_DOWNLOADING:
                progress_percentage = get_progress_percentage(file_state.bytes_downloaded, file_state.file_info['size'])
            else:
                progress_percentage = ""

            summary += "\n    %s%s%s%s" % (str.ljust(str(file_state.filepath), max_filepath_length + 4),
                                           str.ljust(file_size_human, 11),
                                           str.ljust(file_state.status, 25),
                                           progress_percentage)

        return summary

    def construct_file_downloads_history_summary(self, file_download_history):

        '''
        #### DOWNLOAD HISTORY #####
        
         
        6227709558521856 Job 08285 Task 001 20MB  CACHED /work/renders/light_v001/beauty/deep_lidar.deep.0005.exr  <timestamp>
        7095580349853434 Job 08285 Task 002 10MB  DL     /work/renders/spider_fly01/beauty/deep_lidar.deep.0005.exr  <timestamp>
        5343402947290140 Job 08284 Task 001 5MB   DL     /work/renders/light_v002/data/light_002.deep.0005.exr  <timestamp>
                     
        '''

        table_data = []

        for file_download_state in file_download_history:
            row_data = {}
            row_data["Completed at"] = get_human_timestamp(file_download_state.time_completed)
            row_data["Download ID"] = file_download_state.download_id
            row_data["Job"] = file_download_state.file_info["job_id"]
            row_data["Task"] = file_download_state.file_info["task_id"]
            row_data["Size"] = get_human_bytes(file_download_state.file_info["size"])
            row_data["Action"] = "Reused" if file_download_state.use_existing else "DL"
            row_data["Duration"] = get_human_duration(file_download_state.get_duration())
            row_data["Thread"] = file_download_state.thread_name
            row_data["Filepath"] = file_download_state.filepath
            table_data.append(row_data)


        table = HistoryTablePrinter(table_data)
        table.title = "##### DOWNLOAD HISTORY ##### %s" % (("(last %s files)" % self.history_queue_max) if self.history_queue_max else "")

        return table.make_table_str()



# @dec_random_exception(percentage_chance=0.05)
@dec_retry(tries=3, static_sleep=1)
def delete_file(filepath):
    os.remove(filepath)

@dec_retry(tries=3, static_sleep=1)
def chmod(filepath, mode):
    os.chmod(filepath, mode)

def prepare_dest_dirpath(dir_path):
    '''
    Prepare the destination directory, ensureing that it exists and it has
    open permission.
    '''
    logger.debug("Creating destination directory if necessary: %s", dir_path)
    safe_mkdirs(dir_path)
    logger.debug("chmodding directory: %s", dir_path)
    chmod(dir_path, 0777)


# @dec_random_exception(percentage_chance=0.05)
@dec_retry(retry_exceptions=CONNECTION_EXCEPTIONS)
def _get_next_downloads(location, endpoint, client, count=1):
    params = {'location': location,
              "count": count}
    # logger.debug('params: %s', params)
    response_string, response_code = client.make_request(endpoint, params=params)
#     logger.debug("response code is:\n%s" % response_code)
#     logger.debug("response data is:\n%s" % response_string)
    if response_code != 201:
        return None

    return json.loads(response_string).get("data", [])

@dec_retry(retry_exceptions=CONNECTION_EXCEPTIONS)
def _get_job_download(endpoint, client, jid, tid):
    params = None
    if tid:
        params = {'tid': tid}
#     logger.debug('params: %s', params)
    response_string, response_code = client.make_request(endpoint, params=params)
#     logger.debug("response code is:\n%s" % response_code)
#     logger.debug("response data is:\n%s" % response_string)
    if response_code != 201:
        return None
    download_job = json.loads(response_string)
    return download_job



# @dec_random_exception(percentage_chance=0.05)
@dec_retry(retry_exceptions=CONNECTION_EXCEPTIONS)
def download_file(download_url, filepath, poll_rate=2, state=None):
    '''
        
    state: class with .bytes_downloaded property. Reflects the amount of bytes that have currently
                      been downloaded. This can be used by other threads to report
                      "progress".  Note that this must be a mutable object (hence
                      a class), so that this function, as well as other threads
                      will read/write to the same object. 
    '''
    logger.info('Downloading: %s', filepath)
    response = requests.get(download_url, stream=True)

    logger.debug("download_url: %s", download_url)

    hash_obj = hashlib.md5()

    progress_bytes = 0
    last_poll = time.time()
    with open(filepath, 'wb') as file_pointer:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            total_bytes = float(response.headers.get('content-length', 0))
            if chunk:
                progress_bytes += len(chunk)
                file_pointer.write(chunk)
                if state != None:
                    state.bytes_downloaded += len(chunk)
                now = time.time()
                if now >= last_poll + poll_rate:
                    progress_percentage = get_progress_percentage(progress_bytes, total_bytes)
                    logger.debug('Downloading %s %s', progress_percentage, filepath)
                    last_poll = now

                hash_obj.update(chunk)
    response.raise_for_status()
    logger.debug('Downloading 100%% %s', filepath)
    new_md5 = hash_obj.digest()
    logger.debug('Md5 Checking: %s', filepath)
    return base64.b64encode(new_md5)




def safe_mkdirs(dirpath):
    '''
    Create the given directory.  If it already exists, suppress the exception.
    This function is useful when handling concurrency issues where it's not
    possible to reliably check whether a directory exists before creating it.
    '''
    try:
        os.makedirs(dirpath)
    except OSError:
        if not os.path.isdir(dirpath):
            raise




# @dec_random_exception(percentage_chance=0.05)
def _in_queue(queue, item_dict, key):
    '''
    Helper function
    For the given queue object, return True if the given item is aleady in the
    queue. Use the given key to match dict item values
    '''
    for item in tuple(queue.queue):
        if item[key] == item_dict[key]:
            return True



def run_downloader(args):
    '''
    Start the downloader process. This process will run indefinitely, polling
    the Conductor cloud app for files that need to be downloaded.
    '''
    # convert the Namespace object to a dictionary
    args_dict = vars(args)

    # Set up logging
    log_level_name = args_dict.get("log_level") or CONFIG.get("log_level")
    log_level = loggeria.LEVEL_MAP.get(log_level_name)
    logger.debug('Downloader parsed_args is %s', args_dict)
    log_dirpath = args_dict.get("log_dir") or CONFIG.get("log_dir")
    set_logging(log_level, log_dirpath)

    job_ids = args_dict.get("job_id")
    thread_count = args_dict.get("thread_count")


    if job_ids:
        Downloader.download_jobs(job_ids,
                            task_id=args_dict.get("task_id"),
                            thread_count=thread_count,
                            output_dir=args_dict.get("output"))

    else:
        Downloader.start_daemon(thread_count=thread_count,
                                location=args_dict.get("location"),
                                output_dir=args_dict.get("output"))


def set_logging(level=None, log_dirpath=None):
    log_filepath = None
    if log_dirpath:
        log_filepath = os.path.join(log_dirpath, "conductor_dl_log")
    loggeria.setup_conductor_logging(logger_level=level,
                                     console_formatter=LOG_FORMATTER,
                                     file_formatter=LOG_FORMATTER,
                                     log_filepath=log_filepath)





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



def get_human_bytes(bytes):
    '''
    '''
    if bytes > BYTES_1GB:
        return  "%.2fGB" % (bytes / float(BYTES_1GB))

    elif bytes > BYTES_1MB:
        return  "%.2fMB" % (bytes / float(BYTES_1MB))

    return  "%.2fKB" % (bytes / float(BYTES_1KB))


def get_progress_percentage(current, total):
    '''
    Return  a string percentage, e.g. "80%" given current bytes (int) and total
    bytes (int)

    '''
    if total:
        progress_int = int(current / float(total) * 100)
    else:
        progress_int = 0

    return "%s%%" % progress_int


def get_human_duration(seconds):
    '''
    convert the given seconds (float) into a human friendly unit
    '''
    return str(datetime.timedelta(seconds=int(seconds)))
    return str(datetime.timedelta(seconds=int(seconds)))

def get_human_timestamp(seconds_since_epoch):
    '''
    convert the given seconds since epoch (float)
    '''
    return str(datetime.datetime.fromtimestamp(int(seconds_since_epoch)))



