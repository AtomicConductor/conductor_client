#!/usr/bin/env python

""" Command Line Process to run downloads.
"""
import sys
import random
import signal
import threading
import time
import base64
import hashlib
import functools
import imp
import logging
import multiprocessing
import os
from pprint import pformat
import Queue
import requests

from conductor import CONFIG
from conductor.lib import common, loggeria, downloader2, api_client

# Duration that workers sleep when there's no work to perform
WORKER_SLEEP_DURATION = 60

# The amount of bytes to transfer as a chunk
DOWNLOAD_CHUNK_SIZE = 1048576 * 2  # 2MB

# Maximum times that a file will be retried if errors occur when downloading
MAX_DOWNLOAD_RETRIES = 5

# The frequency (in seconds) for which the Touch thread should
# report progress of the file (outside of start/finish)
TOUCH_INTERVAL = 120

# Log format when not running in DEBUG mode
LOG_FORMATTER = logging.Formatter('%(asctime)s  %(message)s')

# Log format when  running in DEBUG mode
DEBUG_LOG_FORMATTER = logging.Formatter(
    '%(asctime)s  %(name)s%(levelname)9s  %(processName)s %(threadName)s:  %(message)s')

# Reusable authentication token  used across all processes/threads
BEARER_TOKEN = multiprocessing.Array('c', 2000)

# Global run-state variable that decorators and other functions can use to
# know when they should exit
RUN_STATE = multiprocessing.Array('c', 'stoppingorstuff')

LOGGER = logging.getLogger(__name__)


def make_auth_header(bearer_token):
    '''
    Create and return a dictionary which contains the authorization token info
    '''
    return {"authorization": "Bearer %s" % bearer_token}


class DecAuthorize(object):
    '''
    Decorator that adds an authentication header to the wrapped function's
    "headers" argument. Automatically renews tokens when encountering 401 errors
    and retries the function
    '''
    def __call__(self, function):

        @functools.wraps(function)
        def decorater_function(*args, **kwargs):
            '''
            The decorator function
            '''

            # Get the bearer token (either from cache or create a new one if necessary)
            bearer_token = get_bearer_token()

            # update the functions headers dictionary, overwriting/adding an
            # "authorization" key/value
            kwargs["headers"].update(make_auth_header(bearer_token.value))

            # attempt to call the original function with the updated header
            try:
                return function(*args, **kwargs)
            except requests.HTTPError as error:
                # If a 401 exception occurs, fetch a new token, update the auth header with it,
                # and call the original function again
                if  error.response.status_code in [301, 302, 401]:
                    LOGGER.debug("Bearer token expired (401). Fetching a new one: %s", error)
                    bearer_token = get_bearer_token(refresh=True)
                    kwargs["headers"].update(make_auth_header(bearer_token.value))
                    return function(*args, **kwargs)

                # If the exception is not a 401 then raise it
                raise
        return decorater_function



class DecDownloaderRetry(common.DecRetry):
    '''
    Some Docs.
    '''
    def __init__(self, run_value, retry_exceptions=Exception, skip_exceptions=(),
                 tries=8, static_sleep=None):
        self.run_value = run_value
        super(DecDownloaderRetry, self).__init__(retry_exceptions=retry_exceptions,
                                                 skip_exceptions=skip_exceptions,
                                                 tries=tries,
                                                 static_sleep=static_sleep)
    def sleep(self, seconds):
        '''
        sleep for the given number of seconds.

        Instead of doing one long sleep call, we make a loop of many short sleep
        calls. This gives the opportunity to check the running state, and exit
        the sleep process if necessary.
        '''
        global RUN_STATE

        sleep_interval = seconds / 10.0

        for _ in range(10):
            if RUN_STATE.value != self.run_value:
                raise DownloaderExit(0)
            time.sleep(sleep_interval)



class FailDownload(Exception):
    '''
    Custom exception to raise when a download should be failed. This may be due to
    a variety of reasons, such as the remote file not existing, or not having adequate
    permissions for writing to a local disk, etc.
    This exception is used to bypass the retry decorator so that the download is NOT retried.
    '''


class DownloaderExit(SystemExit):
    '''
    Custom exception to handle (and raise) when the DownloadWorker processes
    should be halted.  This subclasses the SystemExit builtin exception. Raising it
    will exit the process with the given return code.
    '''


class Downloader(object):
    """
    Top-level Downloader class that maintains all worker processes/threads and
    terminates them using shared state objects (signaled via SIGINT -KeyboardInterrupt).

    Below is the structure of the Downloader and all of it's child process/threads

    Downloader                    # Main process
        |
        |_DownloadWorker-1        # Process
        |    |_TouchWorker-1      # Thread
        |
        |_DownloadWorker-2        # Process
        |    |_TouchWorker-2      # Thread
        |
        |_DownloadWorker-N        # Process
        |    |_TouchWorker-N      # Thread
        |
        |_HistoryWorker           # Process


    NOTE: For the sake of the brevity we'll refer to "threads" as "processes" for
    the rest of this documentation

    In order to shutdown these child processes, each process (including their
    own child processes has a corresponding multiprocessing.Array object that the
    parent uses to signal the child to shutdown.  Though processes can be terminated
    by having each one simply throwing an exception, we want to make sure that
    each process terminates cleanly (releasing resources and signaling to their
    own child processes). Therefore, every child process should only exit by returning
    from it's "run" method (don't raise an exception!).

    Also, every parent should "join" any of it's child processes before exiting
    itself.  This ensures that all children processes have indeed terminated
    properly. Otherwise this could lead to "zombie" processes (no parents).

    Life-cycle of a Process:
        1. a process (Process1) is started by parent process (Parent1). Parent1 retains a
          shared object to signal run-state change to Process1
        2. Process1 creates and starts it's own child process (Child1)
        3. Process1 runs indefinitely (looping within it's "run" method),
          constantly checking the status of it's run-state object.
        4. a KeyboardInterupt (SIGINT) is triggered by the user, and is handled
          by Parent1.  Parent1 signals to Process1 to shutdown (by changing the value of the
          run-state object).
        5. Process1 detects that the run-state value has changed, and calls it's
          own "_stop" method.
        6. The stop method changes the run-state object for the Child1 process,
           (triggering Child1 to go through the same shutdown logic (step 5)
        7. Before returning from the "run" method, Process1 "joins" the Child1 process
           so that it blocks (and waits for Child1 to exit).

    The parent/calling process uses a process-safe multiprocessing.Array object
    to communicate to this process when needing to shutdown/cleanup/exit.
        Available state values:
            - "running":       all systems go.
            - "stopping":      stop everything and cleanup.

    The DownloadWorker process has a child thread of it's own (TouchWorker),
    which is responsible for communicating the progress of the current file download
    to the conductor backend.  It, too, uses the a multiprocessing.Array object
    to control signal when it should be stopped or not.
    """

    # Run State values
    STATE_RUNNING = "running"
    STATE_STOPPING = "stopping"

    # the maximum number of dl result data to maintain (for history purposes, etc)
    RESULTS_MAX = 100

    def __init__(self, args):
        self._start_time = None
        self._workers = []

        # Contains the user-provided arguments
        self.args = args

        # Create a results queue that will hold the results of all files
        # that are downloaded from each DownloadWorker
        self._results_queue = multiprocessing.Queue(self.RESULTS_MAX)

        # Register the SIGINT signal with our sigint handler
        signal.signal(signal.SIGINT, self.sigint_handler)

    def start_daemon(self):
        """
        Start the downloader daemon. Create all child worker processes, start
        them, and join them. This is blocking function and will not exit until
        all workers have exited their prococess.

        """
        LOGGER.info("starting downloader daemon")

        global RUN_STATE
        RUN_STATE.value = self.STATE_RUNNING

        # Record the start time of instantiation, so that we can report uptime
        self._start_time = time.time()

        # Create and start all workers
        self._workers = self._create_workers(start=True)
        LOGGER.debug("Started workers:\n\t%s", "\n\t".join(sorted([w.name for w in self._workers])))

    def stop_daemon(self):
        """
        Stop the downloader daemon and exit the application.

        1. change the run_state value of each worker's shared object value.
           This will trigger each worker's stop/cleanup behaviors.
        2. Exit the application runtime by raising an exception (we must break
           out of the join that occurred in the start_daemon method).
        """

        # Cycle through each worker, and change the share object's state value to "stopping
        for worker, run_state in self._workers.iteritems():
            LOGGER.debug(
                "changing %s from %s to %s",
                worker.name,
                run_state.value,
                self.STATE_STOPPING)
            run_state.value = self.STATE_STOPPING

        # Join the workers. It's generally good practice to do this. Otherwise the
        # parent process can exit (and return control back to shell) before
        # the child processes exit (creating zombie processes).
        # see here: https://docs.python.org/2/library/multiprocessing.html#all-platforms
        for wrk in self._workers:
            wrk.join()

        LOGGER.debug(
            "All procs exited:\n\t%s",
            "\n\t".join(sorted([w.name for w in self._workers])))

        # Log out the uptime of the daemon
        self.log_uptime()

    def _create_workers(self, start=True):
        """
        Create child worker processes.  For each worker, create a process/thread
        safe object that is used to communicate between this parent process and
        the worker.  Return a dictionary where the key is the process object,
        and the value its corresponding run_state state object.

        WORKERS:
            - DownloadWorker # Downloads files
            - HistoryWorker  # logs out history of downloaded files
        """
        bearer = get_bearer_token()
        account = api_client.account_id_from_jwt(bearer.value)
        LOGGER.info("account: %s", account)

        project = self.args.get("project") or None
        LOGGER.info("project: %s", project)

        location = self.args.get("location") or None
        LOGGER.info("location: %s", location)

        output_dir = self.args.get("output") or ""
        LOGGER.info("output_dir: %s", output_dir)

        thread_count = self.args.get("thread_count") or 5
        LOGGER.info("thread_count: %s", thread_count)

        #### CREATE WORKER PROCESSES ####
        workers = {}

        # Create DownloadWorker processes
        for _ in range(thread_count):

            # Create a process-safe run_state object for controlling process
            run_state = multiprocessing.Array('c', "stoppingorstuff")
            wrk = DownloadWorker(run_state,
                                 self._results_queue,
                                 account=account,
                                 output_dir=output_dir,
                                 project=project,
                                 location=location)
            workers[wrk] = run_state

        # Create a HistoryWorker process for printing out the history of downloaded files
        run_state = multiprocessing.Array('c', "stoppingorstuff")
        worker = HistoryWorker(run_state=run_state,
                               results_queue=self._results_queue,
                               print_interval=10,
                               history_max=self.RESULTS_MAX)
        workers[worker] = run_state

        if start:
            for wrkr in workers:
                wrkr.start()
                time.sleep(.5)

        return workers

    def sigint_handler(self, sig, frm):
        '''
        Handles the SIGINT signal (i.e. the KeyboardInterrupt python exception).

        This simply calls the Downloader's stop_daemon method.

        Note that when registering this function as the signint handler, this function
        gets called by ALL child processes as well.  Because of this, we check
        which process is calling it, and only execute it if it's the main (parent)
        process.
        '''

        # change the global
        global RUN_STATE
        RUN_STATE.value = "killed"

        current_process = multiprocessing.current_process()

        # if the process that is calling this function is the "MainProcesS"
        if current_process.name == "MainProcess":
            LOGGER.warning("ctrl-c exit...")
            LOGGER.debug("Stopping...")
            return self.stop_daemon()

    def log_uptime(self):
        '''
        Return the amount of time that the uploader has been running, e.g "0:01:28"
        '''
        seconds = time.time() - self._start_time
        human_duration = common.get_human_duration(seconds)
        LOGGER.info("Uptime: %s", human_duration)


class DownloadWorker(multiprocessing.Process):
    """
    A multiprocessing.Process worker class that is responsible for:

      - Ask the downloader service for the next download in the queue.
      - stream the downloadable file to disk (or check whether it already exists).
      - periodically report progress to the service.
      - record the results of each file download and log out history summaries
      - notify service of file completion and failure (when possible)

    The parent/calling process uses a process-safe multiprocessing.Array object
    to communicate to this process when needing to shutdown/cleanup/exit.
        Available state values:
            - "running":       all systems go.
            - "stopping":      stop everything and cleanup.

    The DownloadWorker process has a child thread of it's own (TouchWorker),
    which is responsible for communicating the progress of the current file download
    to the conductor backend.  It, too, uses the a multiprocessing.Array object
    to control signal when it should be stopped or not.
    """
    def __init__(self, run_state, result_queue, account, log_interval=5,
                 output_dir=None, project=None, location=None):
        """
        Initialize download worker process.

        args:

            run_state:    multiprocessing.Array object. Used by the parent calling
                          process to communicate when to shutdown/exit this Process.

            result_queue: multiprocessing.Queue object. Stores the result of each
                          downloaded file. This is process/thread safe object
                          that can be used to communicate the results of each
                          file download with other processes/parents etc.

            account:      str. account name.

            log_interval: int.  The interval in seconds to log out progress %
                          while downloading the file. If no progress logging is
                          desired, set to None.

            output_dir:   str. If provided, will use this directory to download
                          the file to.  Otherwise, it will download the file to
                          it's own recorded output path.

            project:      str. if provided, will only download files with the given
                          project name

            location:     str. if provided, will only download files with the given
                          location name
        """
        super(DownloadWorker, self).__init__()

        # Record provided arguments
        self._run_state = run_state
        self._progress_queue = multiprocessing.Queue()
        self._result_queue = result_queue
        self._log_interval = log_interval
        self.location = location
        self.account = account
        self.output_dir = output_dir
        self.project = project

        # Set the bytes counter to 0
        # The bytes counter tracks the current amount of bytes have processed
        # (hashed or downloaded) for the current file download.
        self._bytes_counter = Counter(0)

        self._workers = []

    def run(self):
        '''
        Overloaded method that is called by the inherited start() method.

        This serves as the outer/upper wrapper function which is responsible for:
            1. Creating and starting any child workers of its own (TouchWorker, etc).
            2. Calling the "inner" run function to continually query for and
               download files that are pending download.
            3. Monitoring the run_state value to determine whether to exit the
               loop or not.
            4. Catching all unexpected exceptions and preventing the process from
               dying

            5. Catching any DownloaderExit exceptions to break out of the while loop
            6. calling  the _stop method to properly stop any/all child processes/threads.

        In order to shutdown the Downloader in general, it's important that this
        method is exited properly (reaches the end of the method). i.e. don't
        allow any exceptions to be raised.
        '''
        time.sleep(
            random.randint(0,200) / 100.0
        )

        # Set the run_state value to "running"
        self._run_state.value = Downloader.STATE_RUNNING

        # Create the worker processes/threads, and start them
        self._workers = self._create_workers(start=True)

        # While the downloader is in a running state, continue to try to download
        # a file.  If an exception occurs, catch and log it, and restart the loop
        while self._run_state.value == Downloader.STATE_RUNNING:
            try:
                self._run()

            # Catch DownloaderExit exception, and exit the while loop
            except DownloaderExit:
                break

            # catch all other exceptions here. This should hopefully never happen.
            # But catch it so that the worker process doesn't die.
            except:
                LOGGER.exception("Preventing process from exiting due to Exception:\n")
                # wait a little to allow for exception recovery .
                # TODO:(lws) this may be totally stupid/unnecessary)
                self._wait()

        # call stop method to properly shutdown child processes, cleanup, etc
        self._stop()

        # Drain the queue.
        # Note that the process may not die properly unless the queue is
        # emptied first. Hang forever from parent's call to Join.
        empty_queue(self._progress_queue)

        LOGGER.debug("Exiting process")

    def _create_workers(self, start=True):
        """
        Create child worker processes.  For each worker, create a process/thread
        safe object that is used to communicate between this parent process and
        the worker.  Return a dictionary where the key is the process object,
        and the value its corresponding run_state state object.

        WORKERS:
            - TouchWorker # Reports live progress of current file download to
                            conductor backend
        """
        workers = {}

        run_state = multiprocessing.Array('c', "stoppingorstuff")
        worker = TouchWorker(run_state,
                             self._progress_queue,
                             interval=TOUCH_INTERVAL,
                             process_name=self.name,
                             account=self.account,
                             location=self.location,
                             project=self.project)
        workers[worker] = run_state

        if start:
            _ = [wrk.start() for wrk in workers]

        return workers

    def _run(self):
        '''
        Query for and download the next pending file.

        One of three things can happen to a file:
            - download the file (transfer the file to local disk)
            - skip/reuse the file bc it's already on local disk (after md5 checking)
            - fail the file (due to any variety of reasons)

        Each file that is handled will have its "result" added to the results queue.
        '''
        # Reset the file state info
        self._reset_progress()

        # Query for the next pending file to download
        next_dl = self._get_next_download()

        # If there is not a pending file to download, simply wait and return.
        if not next_dl:
            self._wait()
            return

        # Otherwise handle the dl
        LOGGER.debug("next_dl:\n%s", pformat(next_dl))

        # do some data mangling before allowing the data to continue any further
        # TODO:(lws) validate payload values
        next_dl = self._adapt_payload(next_dl)

        url = next_dl["url"]

        # extract the file download info
        dl_info = next_dl["dl_info"]

        # unpack some values for convenience
        id_, jid, tid, destination, file_size = (dl_info["id"],
                                                 dl_info["jid"],
                                                 dl_info["tid"],
                                                 dl_info["destination"],
                                                 dl_info['file_size'])

        # Construct the local filepath to download to
        local_file = os.path.normpath(self.output_dir + os.sep + destination)

        # Record the start time of the download process
        time_started = time.time()

        success = False

        # attempt to download the file. The action will either be "DL" or "Reuse"
        try:
            downloaded = self._maybe_download_file(local_file, id_, url, dl_info)

            # Set the action to DL if the file was actually downloaded. Otherwise set it to reuse
            action = "DL" if downloaded else "Reuse"

            success = True

        # Catch a DownloaderExit exception, perform any cleanup, then re-raise
        # the exception
        except DownloaderExit:
            success = False
            self._cleanup_download(id_, jid, tid, destination, local_file)
            raise

        # Catch all other exceptions for the file download, and report the
        # failure via http call. Set the action to "Failed"
        except:
            success = False
            action = "Failed"
            # log out the exception
            LOGGER.exception("%s|%s  CAUGHT EXCEPTION  %s:\n", jid, tid, local_file)
            msg = "Failing id %s" % id_
            self._log_msg(jid, tid, msg, local_file, log_level=logging.ERROR)

        # Reset the file state info.
        self._reset_progress()

        # Record the end time of the download process
        time_ended = time.time()

        if success:
            # Report to the app that that the file finished
            Backend.finish(id_, bytes_downloaded=file_size, account=self.account, location=self.location, project=self.project)
        else:
            Backend.fail(id_, bytes_downloaded=self._bytes_counter.value, account=self.account, location=self.location, project=self.project)

        # construct and return a "result" dictionary of what how this file downloaded was handled
        result = self._construct_result_dict(dl_info, id_, local_file, action,
                                          time_started, time_ended)

        # Add the result of the download to the result queue
        self._result_queue.put_nowait(result)

    def _get_next_download(self):
        '''
        fetch and return the next downloadable file (or None if there aren't any)
        '''
        # Fetch the next download (only 1)
        downloads = Backend.next(self.account, location=self.location, project=self.project, number=1) or []
        if downloads:
            # Return the one download in the list
            return downloads[0]

    def _wait(self):
        '''
        sleep for WORKER_SLEEP_DURATION

        Instead of doing one long sleep call, we make a loop of many short sleep
        calls. This gives the opportunity to check the running state, and exit
        the sleep process if necessary.
        '''
        for _ in range(random.randint(10, WORKER_SLEEP_DURATION)):
            if self._run_state.value == Downloader.STATE_RUNNING:
                time.sleep(1)

    def _adapt_payload(self, payload):
        '''
        change the contents of the payload to meet client expectations.
        '''
        # Change the id to use an underscore so that it doesn't conflict with
        # python built-in "id"
        id_ = payload.pop("id", None)
        if id_ != None:
            payload["id_"] = id_

        # Change "download_file" to "dl_info" bc I find it less confusing (lws)
        dl_info = payload.pop("download_file", None)
        if dl_info != None:
            payload["dl_info"] = dl_info

        # Remove extraneous data
        payload.pop("bytes_transferred", None)
        payload.pop("inserted_at", None)
        return payload

    def _maybe_download_file(self, local_file, id_, url, dl_info):
        """
        checks for existing file and validates md5, if valid, skip download.
        Return True if the file is actually downloaded (and None if it is skipped)

        args:
            local_file: str. The file path to download the file to.
            id_:        str.   The id of the file download
            url:        str.   The url to download the file from
            dl_info:    dict of information about the file to download (jid/tid/md5, etc)
        """
        jid, tid, md5, = dl_info["jid"], dl_info["tid"], dl_info["md5"]

        # If the file doesn't already exists on disk and have the proper hash, then download the file
        if not self._file_exists_and_is_valid(id_, local_file, md5, jid, tid):
            self.download(id_, local_file, url, dl_info)
        # return True to indicate that the file was downloaded
        return True

    @DecDownloaderRetry(run_value=Downloader.STATE_RUNNING, skip_exceptions=(DownloaderExit, FailDownload), tries=MAX_DOWNLOAD_RETRIES)
    def download(self, id_, local_file, url, dl_info):
        """
        The "outer" download function that wraps the "real" download function
        in retries (decorator) and md5 verification.  All exceptions that are
        encountered will be automatically retried...except for DownloaderExit

        """
        jid, tid, md5 = dl_info["jid"], dl_info["tid"], dl_info["md5"]

        # Reset the file state info (this may be required because of retry decorator/loop)
        self._reset_progress()

        new_md5 = self._download(id_, local_file, url, dl_info, self._progress_queue)

        # Validate that the new md5 matches the expected md5
        # If the md5 does not match, then delete the file that was just downloaded
        # and raise an exception.  This will trigger a retry (via the decorator).
        if new_md5 != md5:
            try:
                self._log_msg(jid, tid, "Removing bad file", local_file,
                             log_level=logging.DEBUG)
                os.remove(local_file)
            except:
                self._log_msg(jid, tid, "Could not cleanup bad file", local_file,
                             log_level=logging.WARNING)

            # Raise an exception. This will cause a retry
            raise Exception("Downloaded file does not have expected md5. "
                            "%s vs %s: %s" % (new_md5, md5, local_file))

        self._log_msg(jid, tid, "MD5 Verified", local_file, log_level=logging.DEBUG)

    def _download(self, id_, local_file, url, dl_info, progress_queue):
        """
        Download the given file url to the given local_file path.
        Return the md5 (base64) of the downloaded file.

        Per each chunk of the file, increment the bytes_counter and add the total
        bytes to the progress_queue object.  The progress_queue is read  by
        the TouchWorker thread  to indicate whether to "touch" the backend, and
        if so, how many bytes to report as downloaded.
        """
        # unpack some values for convenience
        jid, tid, file_size = dl_info["jid"], dl_info["tid"], dl_info["file_size"]

        # Request the url
        response = requests.get(url, stream=True)

        # Raise 500 errors. These will get retried via the decorator
        if response.status_code >= 500:
            response.raise_for_status()

        # Automatically fail the download if we don't get a 200  (don't retry it!)
        if response.status_code not in [200]:
            msg = "Bad response code %s: %s" % (response.status_code, response.text)
            self._log_msg(jid, tid, msg, local_file, log_level=logging.DEBUG)
            raise FailDownload(msg)

        # Create the local directory if it does not exist
        safe_mkdirs(os.path.dirname(local_file))

        # create a hashlib object that we can put chunks into for on-the-fly md5 calculation
        hash_obj = hashlib.md5()

        # record the time so that we know whether to log out progress or not.
        last_poll = time.time()

        # Initial log to indicate 0% complete
        self._log_progress(local_file, jid, tid, file_size)

        with open(local_file, 'wb') as file_obj:
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                # If the run state = stopping. raise a system exit error.
                # This will not trigger
                if self._run_state.value == Downloader.STATE_STOPPING:
                    raise DownloaderExit(0)

                # filter out bad chunks due to http errors
                if chunk:

                    # Write the chunk to the file
                    file_obj.write(chunk)

                    # Increment the bytes counter so that we can track transfer progresss
                    self._bytes_counter += len(chunk)

                    # Put the the bytes counter value into the progree queue
                    progress_queue.put_nowait((id_, "dl", self._bytes_counter.value))

                    # Update the hash for md5 calculations
                    hash_obj.update(chunk)

                    # Check the time interval and log out progress if appropriate
                    now = time.time()
                    if self._log_interval != None and now >= last_poll + self._log_interval:
                        self._log_progress(local_file, jid, tid, file_size)
                        last_poll = now

            # Record the time in which
            close_start = time.time()

        close_duration = time.time() - close_start

        # if it took more than 30 seconds to close the file, give a warning
        if close_duration > 30:
            msg = ("File closing took: %s seconds, yikes! This may cause a file "
                   "download to get reset.  This is likely due to poor disk "
                   "performance. Consider reducing thread thread count for "
                   "Downloader or use a more performant file system!") % common.get_human_duration(close_duration)
            self._log_msg(jid, tid, msg, local_file, log_level=logging.WARNING)

        # Final log to indicate 100% complete
        self._log_progress(local_file, jid, tid, file_size)

        # calculate and return md5
        new_md5 = hash_obj.digest()
        return base64.b64encode(new_md5)

    def _file_exists_and_is_valid(self, id_, local_file, md5, jid, tid):
        '''
        Validate that the give filepath exists on disk and its md5 matches that
        of the given one.  Return True if that's the case.

        While md5 hashing an existing file, update the _bytes_counter and
        _progress_queue so that the TouchWorker can report the progress to the
        conductor backend
        '''
        self._log_msg(jid, tid, "Checking for existing file", local_file, log_level=logging.DEBUG)

        # check whether file exists
        if not os.path.exists(local_file):
            self._log_msg(jid, tid, "File does not exist", local_file, log_level=logging.DEBUG)
            return

        # Create a callback function that the md5 hashing function will call periodically
        callback = functools.partial(self._update_bytes_counter_callback, id_)

        # Check whether the md5 matches
        local_md5 = common.generate_md5(local_file, base_64=True,
                                        poll_seconds=self._log_interval,
                                        callback=callback,
                                        log_level=logging.INFO)
        if local_md5 != md5:
            self._log_msg(jid, tid, "Md5 mismatch (%s vs %s)" % (local_md5, md5),
                         local_file, log_level=logging.WARNING)
            return

        # Otherwise Return True to indicate that the file exists and matches the md5
        self._log_msg(jid, tid, "File already downloaded and verified.", local_file, log_level=logging.DEBUG)
        return True

    def _cleanup_download(self, id_, jid, tid, destination, local_file):
        '''
        Cleanup the download.  This is currently a No-op, but serves as a
        slot for any cleanup that may need to happen for the download
        before for the download worker process exits. As of now, a download
        file will get automatically reset on the backend if the downloader
        hasn't reported activitiy about it after a few mins.
        '''
        message = "Cleaning up id %s" % id_
        self._log_msg(jid, tid, message, local_file, ljust=37, log_level=logging.INFO)

    def _reset_progress(self):
        '''
        Reset the state data of the current file download. Reset the bytes counter
        and empty the progress queue.
        '''
        # Reset the bytes counter
        self._bytes_counter.value = 0

        # flush the progress queue
        empty_queue(self._progress_queue)

    def _log_msg(self, jid, tid, message, local_file, ljust=37, log_level=logging.INFO):
        '''
        Log a message about the given file.  This is a convenience function that
        creates a message that is structured and consistent throughout the downloading
        processes. This makes readability easier when trolling through logs.

        example output:
            <jid>|<tid>  <message  <file path>

        '''
        msg_template = "%(jid)s|%(tid)s  %(message)s  %(filepath)s"
        LOGGER.log(log_level, msg_template, {"message":message.ljust(ljust),
                                                              "jid":jid,
                                                              "tid":tid,
                                                              "filepath":local_file})

    def _log_progress(self, local_file, jid, tid, file_size, log_level=logging.INFO):
        '''
        Log a message about the download progress of the given file. This uses
        the current state info (bytes_transferred) to calculate progress.

        <jid>|<tid>  Downloading  <percentage>  <transferred/total>  <file path>

        example output:

            35748|000  Downloading   76%     859.38MB/1.09GB  /home/users/beanie/face.png

        '''
        progress = common.get_progress_percentage(self._bytes_counter.value, file_size)
        ratio_str = "%s/%s" % (common.get_human_bytes(self._bytes_counter.value),
                               common.get_human_bytes(file_size))

        msg = "Downloading  %s  %s" % (progress.rjust(4), ratio_str.rjust(18))
        self._log_msg(jid, tid, msg, local_file, log_level=log_level)

    def _construct_result_dict(self, dl_info, id_, local_file, action, time_started, time_ended):
        '''
        Construct a "result" dictionary that contains information about how the
        download was handled. Contains the following keys:
            - "Id": The id of the file that was downloaded
            - "Filepath": The filepath that the file was downloaded to.
            - "Started at": The time that the download was started
            - "Completed at": The time that the download finished
            - "Duration": How long it took to download the file
            - "Action": whether the file was downloaded or reused (bc it already existed)
            - "Thread": The name of the thread(process) that downloaded the file
            - "Download ID:  the id of the Download resource that the file is part of.
            - "Job:  the job id. str. e.g. "02302"
            - "Task: the task id. str. e.g. "002"
            - "Size: int. The size of the file (in bytes).
        '''
        result = {}
        result["ID"] = id_
        result["Download ID"] = dl_info["dlid"]
        result["Job"] = dl_info["jid"]
        result["Task"] = dl_info["tid"]
        result["Size"] = dl_info["file_size"]
        result["Filepath"] = local_file
        result["Action"] = action
        result["Started at"] = time_started
        result["Completed at"] = time_ended
        result["Duration"] = time_ended - time_started
        result["Thread"] = self.name
        return result

    def _update_bytes_counter_callback(self, id_, filepath, file_size, bytes_processed, log_level):
        '''
        A callback function that the md5 hashing function uses to update the
        _byte_counter and progress_queue.

        Check the run_state value and raise a DownloaderExit exception in order
        to exit/break out of the md5 hashing process
        '''
        if self._run_state.value != Downloader.STATE_RUNNING:
            LOGGER.warning("Exiting hashing")
            raise DownloaderExit(0)
        self._bytes_counter.value = bytes_processed
        self._progress_queue.put_nowait((id_, "hash", bytes_processed))

    def _stop(self):
        """
        Cycle through all child worker processes and change their run_state objects
        to signal them to stop. Join all child processes to block until they all
        exit properly
        """
        for worker, state in self._workers.iteritems():
            LOGGER.debug("changing %s from %s to %s", worker.name, state.value, Downloader.STATE_STOPPING)
            state.value = Downloader.STATE_STOPPING

        LOGGER.debug("waiting for procs to exit:\n\t%s", "\n\t".join(sorted([w.name for w in self._workers])))
        [wrk.join() for wrk in self._workers]
        LOGGER.debug("All procs exited:\n\t%s", "\n\t".join(sorted([w.name for w in self._workers])))


class TouchWorker(threading.Thread):
    '''
    A Thread that periodically reports/"touches" file progress to the Conductor
    backend. Aside from reporting the byte progress of a file, it also serves
    as a "heartbeat" for a file download, indicating to the backend that the file
    is still in progress and to not consider it a stranded/dead file download.

    The frequency of the reporting is dictated by two things:
        1. The self._interval variable (seconds). A potential "touch" will occur
           every _interval seconds
        2. However, the touch will only be executed  if there is data in the
           progress_queue. If there is no data in the progress queue then a "touch"
           will not not be issued. The progress queueu should have constant data
           streaming through it (either when md5 hashing or downloading the file).
           If there is no data getting put into it, then it means that the DownloadWorker
           has hung on that file for some reason.  Eventually the backend will
           "reset" that download because it will not have been touched after a
           few minutes.
    '''

    def __init__(self, run_state, progress_queue, interval=10, process_name="", account=None, project=None, location=None):
        '''
        run_state:    multiprocessing.Array object. Used by the parent calling
                      process to communicate when to shutdown/exit this Process.

        progress_queue: multiprocessing.Queue object.

        interval: int/float. The frequency to potentially issue a Touch to the backend
        process_name: str. the name of the parent process. This will serve as
                      a prefix for the thread's name.
        '''

        self._progress_queue = progress_queue
        self._interval = interval
        self._run_state = run_state
        self._account = account
        self._project = project
        self._location = location
        super(TouchWorker, self).__init__(name=process_name + " TouchWorker")

    def run(self):
        '''
        Perpetually report the file progress to the app for a given interval.

        Report on the last entry found in the progress queue. If there are no entries,
        then do not report anything. We want the backend to reset any "stranded"/"stuck"
        downloads, so only report progress when there IS progress. Progress entries
        only get added to the queue when a file download is being actively hashed
        or downloaded.
        '''
        self._run_state.value = Downloader.STATE_RUNNING

        self._last_touch = time.time()

        while self._run_state.value == Downloader.STATE_RUNNING:
            if time.time() - self._last_touch >= self._interval:

                # Get the most recent file progress from the queue
                file_progress = self._get_last_file_progress(self._progress_queue)

                # If there is file progress, "touch" the backend with the progress data
                if file_progress:
                    file_id, action, bytes_processed = file_progress
                    try:
                        self._touch(file_id, action, bytes_processed)
                    except:
                        LOGGER.exception("FAILED TO TOUCH:\n")

                self._last_touch = time.time()

            # sleep a lil so that we're not slamming the cpu
            self._wait(seconds=.2)

        LOGGER.debug("Exiting thread")

    def _touch(self, file_id, action, bytes_processed):
        LOGGER.debug("Touching backend: id=%s _bytes_action=%s bytes_processed=%s" % (file_id, action, bytes_processed))
        Backend.touch(file_id, bytes_transferred=bytes_processed, account=self._account, location=self._location, project=self._project)

    def _wait(self, seconds):
        '''
        sleep for the given number of seconds.

        Instead of doing one long sleep call, we make a loop of many short sleep
        calls. This gives the opportunity to check the running state, and exit
        the sleep process if necessary.
        '''
        sleep_interval = seconds / 10.0

        for _ in range(10):
            if self._run_state.value == Downloader.STATE_RUNNING:
                time.sleep(sleep_interval)

    @classmethod
    def _get_last_file_progress(cls, queue):
        '''
        Get the last item from the given queue object. We're only interested in
        the most recent item in the queue (all older ones are superseded by newer
        entries), but unfortunately there are no FILO queues for multiprocessing.
        No matter, we need to clear the contents of the queue anyway, so we'll
        remove all items and return the last item
        '''
        progress_items = empty_queue(queue)
        if progress_items:
            # return the last item
            return progress_items[-1]


class HistoryWorker(multiprocessing.Process):
    '''
    A process that periodically print/logs the "history" of the last x files
    that have been downloaded/uploaded.
    '''

    def __init__(self, run_state, results_queue,
            print_interval=10, history_max=100, worker_type='download', column_names=None):
        '''
        run_state:    multiprocessing.Array object. Used by the parent calling
                      process to communicate when to shutdown/exit this Process.

        results_queue: multiprocessing.Queue object.  Contains an entry for each
                       file that was handled by the worker and what happened
                       with it.

        print_interval: int/float. The frequency to print/log the history

        history_max: indicates how many files (the last n) to report about.
        '''
        self._run_state = run_state
        self._results_queue = results_queue
        self._history_max = history_max
        self._print_interval = print_interval
        self._last_history = None
        self._worker_type = worker_type
        self._label = worker_type.upper()
        self._column_names = column_names \
            or ["Completed at", "Download ID", "Job", "Task",
                "Size", "Action", "Duration", "Thread", "Filepath"]
        super(HistoryWorker, self).__init__()

    def run(self):
        '''
        Start and return a thread that is responsible for pinging the app for
        files to transfer (and populating the queue)
        '''
        self._run_state.value = Downloader.STATE_RUNNING

        while self._run_state.value == Downloader.STATE_RUNNING:
            self._print_history()

        LOGGER.debug("Exiting process")

    def _print_history(self):
        '''
        #### HISTORY ####
        2016-11-10 00:49:03,311  conductor.lib.downloader     INFO  HistoryWorker-26:  ##### DOWNLOAD HISTORY ##### (last 100 files)
        COMPLETED AT         DOWNLOAD ID       JOB    TASK  SIZE       ACTION  DURATION  THREAD             FILEPATH
        2016-11-10 00:48:53  6718909069656064  35681  010    542.05KB  Reuse   0:00:00   DownloadWorker-19  /tmp/FX_dirt_main_v067.01050.exr
        2016-11-10 00:48:53  6718829881196544  35681  056    340.87KB  Reuse   0:00:00   DownloadWorker-13  /tmp/FX_dirt_main_v067.01096.exr
        2016-11-10 00:48:53  6654165088468992  35681  057    334.88KB  DL      0:00:01   DownloadWorker-21  /tmp/FX_dirt_main_v067.01097.exr
        2016-11-10 00:48:53  6741280748994560  35681  068    305.68KB  Reuse   0:00:00   DownloadWorker-3   /tmp/FX_dirt_main_v067.01108.exr
        2016-11-10 00:48:53  6736540447277056  35681  063    313.54KB  Reuse   0:00:00   DownloadWorker-10  /tmp/FX_dirt_main_v067.01103.exr
        '''
        results_list = []
        while self._run_state.value == Downloader.STATE_RUNNING:
            try:
                # transfer/empty the results queue into the history list
                while not self._results_queue.empty():
                    results_list.append(self._results_queue.get_nowait())

                # slice the list to contain only the last x values
                results_list = results_list[-self._history_max:]

                # Print the history
                history_summary = self._construct_history_summary(results_list)

                # Only print the history if it is different from before
                if history_summary == self._last_history:
                    LOGGER.info('##### %s HISTORY ##### [No changes]' % self._label)
                else:
                    LOGGER.info("%s\n", history_summary)
                    self._last_history = history_summary

            except:
                LOGGER.exception("Failed to report Summary")

            self._wait(self._print_interval)

    def _construct_history_summary(self, results_list):
        '''
        For the given results list, return a printable/loggable history summary
        for them.

        '''
        title = " %s HISTORY %s " % \
            (self._label, ("(last %s files)" % self._history_max) if self._history_max else "")
        table = downloader2.HistoryTableStr(data=list(reversed(results_list)),
                                            column_names=self._column_names,
                                            title=title.center(100, "#"),
                                            footer="#"*180,
                                            upper_headers=True)

        return table.make_table_str()

    def _wait(self, seconds):
        '''
        pause between empty get_next_download() calls

        Instead of doing one long sleep call, we make a loop of many short sleep
        calls. This gives the opportunity to check the running state, and exit
        the sleep process if necessary.
        '''
        sleep_interval = seconds / 10.0

        for _ in range(10):
            if self._run_state.value == Downloader.STATE_RUNNING:
                time.sleep(sleep_interval)

class Backend:

    @classmethod
    def headers(cls):
        bearer = get_bearer_token()
        return{"accept-version": "v1",
               "authorization": "Bearer %s" % bearer.value}

    @classmethod
    @common.dec_timer_exit(log_level=logging.DEBUG)
    @DecDownloaderRetry(run_value=Downloader.STATE_RUNNING, tries=3)
    def next(cls, account, project=None, location=None, number=1):
        """
        Return the next download (dict), or None if there isn't one.
        """
        path = "downloader/next"
        params = {"account": account, "project": project, "location": location}
        return Backend.get(path, params, headers=Backend.headers())

    @classmethod
    @common.dec_timer_exit(log_level=logging.DEBUG)
    @DecDownloaderRetry(run_value=Downloader.STATE_RUNNING, tries=3)
    def touch(cls, id_, bytes_transferred=0, account=None, location=None, project=None):
        path = "downloader/touch/%s" % id_
        kwargs = {"bytes_transferred": bytes_transferred,
                  "account": account,
                  "location": location,
                  "project": project}
        try:
            return Backend.put(path, kwargs, headers=Backend.headers())
        except requests.HTTPError as e:
            if e.response.status_code == 410:
                LOGGER.warning("Cannot Touch file %s.  Already finished (not active) (410)", id_)
                return
        raise

    @classmethod
    @common.dec_timer_exit(log_level=logging.DEBUG)
    @DecDownloaderRetry(run_value=Downloader.STATE_RUNNING, tries=3)
    def finish(cls, id_, bytes_downloaded=0, account=None, location=None, project=None):
        path = "downloader/finish/%s" % id_
        payload = {"bytes_downloaded": bytes_downloaded,
                   "account": account,
                   "location": location,
                   "project": project}
        try:
            return Backend.put(path, payload, headers=Backend.headers())
        except requests.HTTPError as e:
            if e.response.status_code == 410:
                LOGGER.warning("Cannot finish file %s.  File not active (410)", id_)
                return
        raise

    @classmethod
    @common.dec_timer_exit(log_level=logging.DEBUG)
    @DecDownloaderRetry(run_value=Downloader.STATE_RUNNING, tries=3)
    def fail(cls, id_, bytes_downloaded=0, account=None, location=None, project=None):
        path = "downloader/fail/%s" % id_
        payload = {"bytes_downloaded": bytes_downloaded,
                   "account": account,
                   "location": location,
                   "project": project}
        try:
            return Backend.put(path, payload, headers=Backend.headers())
        except requests.HTTPError as e:
            if e.response.status_code == 410:
                LOGGER.warning("Cannot fail file %s.  File not active (410)", id_)
                return
        raise

    @classmethod
    @common.dec_timer_exit(log_level=logging.DEBUG)
    def bearer_token(cls):
        creds_dict = api_client.get_api_key_bearer_token()
        return creds_dict["access_token"]

    @classmethod
    @DecAuthorize()
    def get(cls, path, params, headers):
        '''
        Return a list of items
        '''
        url = cls.make_url(path)
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    @classmethod
    @DecAuthorize()
    def put(cls, path, data, headers):
        url = cls.make_url(path)
        response = requests.put(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json()

    @classmethod
    @DecAuthorize()
    def post(cls, path, data, headers):
        url = cls.make_url(path)
        response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def make_url(path):
        '''
        TODO: get rid of this hardcoding!!!
        '''
        url_base = CONFIG.get("api_url")
        url = "%s/api/v1/fileio/%s" % (url_base, path)
        return url


class Counter(object):
    '''
    Acts as a mutable integer variable, so that adding/subtracting can be
    done to the same object (retaining pointers to same object/varaiable in memory)

    Use the .value attribute to read/write values from/to
    '''

    def __init__(self, value=0):
        self._value = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value

    def __add__(self, other):
        return self._value + other

    def __sub__(self, other):
        return self._value - other

    def __eq__(self, other):
        return self._value == other

    def __iadd__(self, other):
        self._value += other
        return self

    def __isub__(self, other):
        self._value -= other
        return self

    def __str__(self):
        return str(self._value)


def empty_queue(queue):
    '''
    Remove and return all items from the given Queue object
    '''
    items = []

    while True:
        try:
            items.append(queue.get_nowait())
        except Queue.Empty:
            break
        except:
            LOGGER.exception("recovered from exception:\n%s")
            break
    return items


def get_bearer_token(refresh=False):
    '''
    Return the bearer token from a cached(global) variable..  If there is no
    cached value, then fetch a new bearer token and return it (and cache it).

    Note that that BEARER_TOKEN is not a simple string.  It's a process/thread-safe
    object
    '''
    global BEARER_TOKEN

    if refresh or not BEARER_TOKEN.value:
        BEARER_TOKEN.value = Backend.bearer_token()

    return BEARER_TOKEN


def safe_mkdirs(dirpath):
    '''
    Create the given directory.  If it already exists, suppress the exception.
    This function is useful when handling concurrency issues where it's not
    possible to reliably check whether a directory exists before creating it.
    '''

    # Attempt to create the directory path
    try:
        os.makedirs(dirpath)

    # only catch OSERrror exceptions
    except OSError:
        # This exception might happen for various reasons. So to be sure that
        # it's due to the path already existing, check the path existence.
        # If the path doesn't exist, then raise the original exception.
        # Otherwise ignore the exception bc the path exists.
        if not os.path.isdir(dirpath):
            raise


def run_downloader(args):
    '''
    Run the downloader with the given arguments.
    '''
    # Set up logging
    log_level_name = args.get("log_level")
    log_level = loggeria.LEVEL_MAP.get(log_level_name)
    log_dirpath = args.get("log_dir")
    set_logging(log_level, log_dirpath)

    LOGGER.debug('Downloader args: %s', args)
    get_bearer_token()
    downloader = Downloader(args)
    downloader.start_daemon()


def set_logging(level=None, log_dirpath=None):
    log_filepath = None
    if log_dirpath:
        log_filepath = os.path.join(log_dirpath, "conductor_dl_log")

    if level == logging.DEBUG:
        formatter = DEBUG_LOG_FORMATTER
    else:
        formatter = LOG_FORMATTER

    loggeria.setup_conductor_logging(logger_level=level,
                                     console_formatter=formatter,
                                     file_formatter=formatter,
                                     log_filepath=log_filepath,
                                     multiproc=True)


