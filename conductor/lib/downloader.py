#!/usr/bin/env python

""" Command Line Process to run downloads.
"""
import base64
import hashlib
import imp
import logging
import multiprocessing
import os
import requests
import sys
import signal
import time

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from conductor import CONFIG
from conductor.lib import common, loggeria, downloader2

WORKER_PAUSE_DURATION = 15
DOWNLOAD_CHUNK_SIZE = 2048  # 2KB
MAX_DOWNLOAD_RETRIES = 5
TOUCH_INTERVAL = 2000  # number of DOWNLOAD_CHUNK_SIZE chunks to process before touching file in db. (e.g. ~4MB)
LOG_FORMATTER = logging.Formatter('%(asctime)s  %(message)s')
DEBUG_LOG_FORMATTER = logging.Formatter('%(asctime)s  %(name)s%(levelname)9s  %(processName)s:  %(message)s')

logger = logging.getLogger(__name__)



class DownloaderExit(SystemExit):
    '''
    Custom exception to handle (and raise) when the DownloadWorker processes 
    should be halted.  This subclasses the SystemExit builtin exception. Raising it
    will exit the process with the given return code.
    '''



class DownloadWorker(multiprocessing.Process):
    """
    The DownloadWorker class is a subclass of multiprocessing.Process.
    Its responsibilities are:

      - Ask the downloader service for the next download in the queue.
      - stream the downloadable file to disk.
      - periodically report progress to the service.
      - notify service of file completion and failure (when possible)

    A state variable (multiprocessing.Value) is passed into __init__
    that is used to control both the 'next dl' and 'process dl chunks'
    loops. The possible states are:

        - "running":       all systems go.
        - "shutting_down": stop procecssing next files, complete the one in progress.
        - "stopping":      stop everything and cleanup.

    """
    def __init__(self, run_state, result_queue, account, log_interval=5,
                 output_dir=None, project=None, location=None):
        """
        Initialize download worker process.
        
        args:
            
            run_state:    multiprocessing.Array object. 
            
            result_queue: multiprocessing.Queue object. Stores the result of each
                          downloaded file.
            
            account: str. account name
            
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

        # Record arguments
        self._run_state = run_state
        self._result_queue = result_queue
        self._log_interval = log_interval
        self.location = location
        self.account = account
        self.output_dir = output_dir
        self.project = project

        # initialize state values for file download
        self._chunks = 0
        self._bytes_downloaded = 0


    def run(self):
        '''
        called at Instance.start()
        
        This is the "outer" run function that wraps the "real" run in try/except
        so that it prevents the worker process from dying. 
        
        Continually query for and download files that are pending download.
         
        '''
        # While the downloader is in a running state, continue to try to download
        # a file.  If an exception occurs, catch and log it, and restart the loop
        while self._run_state.value == "running":
            try:
                self.run_()

            # Catch DownloaderExit exception, and let it raise (this will exit the process)
            except DownloaderExit:
                raise

            # catch all other exceptions here. This should hopefully never happen.
            # But catch it so that the worker process doesn't die.
            except:
                logger.exception("Preventing process from exiting due to Exception:\n")
                # wait a little to allow for exception recovery .
                # TODO:(lws) this may be totally stupid/unnecessary)
                self.wait()


    def run_(self):

        '''
        Query for and download the next pending file.
        
        One of three things can happen to a file:
            - download the file (transfer the file to local disk)
            - skip/reuse the file bc it's already on local disk (after md5 checking)
            - fail the file (due to any variety of reasons)
            
        Each file that is handled will have its "result" added to the results queue.
        '''

        # Reset the file state info
        self.reset()

        # Query for the next pending file to download
        next_dl = self.get_next_download()

        # If there is not a pending file to download, simply wait and return.
        if not next_dl:
            self.wait()
            return

        # Otherwise handle the dl
        logger.debug("next_dl: %s", next_dl)

        # do some data mangling before allowing the data to continue any further
        # TODO:(lws) validate payload values
        next_dl = self.adapt_payload(next_dl)

        # extract the file id
        id_ = next_dl["id_"]

        # extract the file download info
        dl_info = next_dl["dl_info"]

        # unpack some values for convenience
        jid, tid, destination = dl_info["jid"], dl_info["tid"], dl_info["destination"]

        # Construct the local filepath to download to
        local_file = os.path.normpath(self.output_dir + os.sep + destination)

        # Record the start time of the download process
        time_started = time.time()

        # attempt to download the file. The action will either be "DL" or "Reuse"
        try:
            action = "DL" if self.maybe_download_file(local_file, **next_dl) else "Reuse"

            # Report to the app that that the file finished
            Backend.finish(id_, bytes_downloaded=self._bytes_downloaded)

        # Catch a DownloaderExit exception, perform any cleanup, then re-raise
        # the exception
        except DownloaderExit:
            logger.debug("caught DownloaderExit")
            self.cleanup_download(id_, jid, tid, destination, local_file)
            logger.debug("re-raising DownloaderExit")
            raise

        # Catch all other exceptions for the file download, and report the
        # failure via http call. Set the action to "Failed"
        except:
            action = "Failed"
            # log out the exception
            logger.exception("%s|%s  CAUGHT EXCEPTION  %s:\n", jid, tid, local_file)
            msg = "Failing id %s" % id_
            self.log_msg(jid, tid, msg, local_file, log_level=logging.ERROR)
            Backend.fail(id_, bytes_downloaded=self._bytes_downloaded)


        # Record the end time of the download process
        time_ended = time.time()

        # construct and return a result dictionary
        result = self.construct_result_dict(dl_info, id_, local_file, action,
                                          time_started, time_ended)

        # Add the result of the download to the result queue
        self._result_queue.put_nowait(result)



    def get_next_download(self):
        '''
        fetch and return the next downloadable file (or None if there aren't any)
        '''

        # Fetch the next download (only 1)
        downloads = Backend.next(self.account, location=self.location, number=1) or []
        if downloads:
            # Return the one download in the list
            return downloads[0]


    def wait(self):
        '''
        pause between empty get_next_download() calls
        
        Instead of doing one long sleep call, we make a loop of many short sleep 
        calls. This gives the opportunity to check the running state, and exit
        the sleep process if necessary.
        '''
        for _ in range(WORKER_PAUSE_DURATION):
            if self._run_state.value == "running":
                time.sleep(1)



    def adapt_payload(self, payload):
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



    def maybe_download_file(self, local_file, id_, url, dl_info):
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
        if not self.file_exists_and_is_valid(local_file, md5, jid, tid):
            self.download(id_, local_file, url, dl_info)
            # return True to indicate that the file was downloaded
            return True



    @common.dec_retry(skip_exceptions=DownloaderExit, tries=MAX_DOWNLOAD_RETRIES)
    def download(self, id_, local_file, url, dl_info):
        """
        "outer" download function that wraps the "real" download function
        in retries and md5 verification.  All exceptions that are encountered
        will be automatically retried...except for SystemExit  

        """
        jid, tid, md5 = dl_info["jid"], dl_info["tid"], dl_info["md5"]

        # Reset the file state info (this may be required because of retry loop)
        self.reset()

        new_md5 = self._download(id_, local_file, url, dl_info)

        # Validate that the new md5 matches the expected md5
        # If the md5 does not match, then delete the file that was just downloaded
        # and raise an exception.  This will trigger a retry (via the decorator).
        if new_md5 != md5:
            try:
                self.log_msg(jid, tid, "Removing bad file", new_md5, local_file,
                             log_level=logging.DEBUG)
                os.remove(local_file)
            except:
                self.log_msg(jid, tid, "Could not cleanup bad file", new_md5,
                             local_file, log_level=logging.WARNING)

            # Raise an exception. This will cause a retry
            raise Exception("Downloaded file does not have expected md5. "
                            "%s vs %s: %s" % (new_md5, md5, local_file))



    def _download(self, id_, local_file, url, dl_info):
        """
        Download the given file url to the given local_file path. 
        Return the md5 (base64) of the downloaded file.
        """

        jid, tid, file_size = dl_info["jid"], dl_info["tid"], dl_info["file_size"]

        # Initial log to indicate 0% complete
        self.log_progress(local_file, jid, tid, file_size)

        # Request the url
        response = requests.get(url, stream=True)

        # Create the local directory if it does not exist
        safe_mkdirs(os.path.dirname(local_file))

        # create a hashlib object that we can put chunks into for on-the-fly md5 calculation
        hash_obj = hashlib.md5()

        # record the time so that we know whether to log out progress or not.
        last_poll = time.time()

        with open(local_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):

                # If the run state = stopping. raise a system exit error.
                # This will not trigger
                if self._run_state.value == "stopping":
                    raise DownloaderExit(0)

                if chunk:  # filter out bad chunks due to http errors
                    self._process_file_chunk(f, chunk, id_)

                    # Update the hash for md5 calculations
                    hash_obj.update(chunk)

                    # Check the time interval and log out progress if appropriate
                    now = time.time()
                    if self._log_interval != None and now >= last_poll + self._log_interval:
                        self.log_progress(local_file, jid, tid, file_size)
                        last_poll = now


        # Final log to indicate 100% complete
        self.log_progress(local_file, jid, tid, file_size)

        # calculate and return md5
        new_md5 = hash_obj.digest()
        return base64.b64encode(new_md5)


    def _process_file_chunk(self, file_obj, chunk, id_):
        """
        process each chunk in a streaming download.
        """
        file_obj.write(chunk)
        self._chunks += 1
        self._bytes_downloaded += len(chunk)
        if not self._chunks % TOUCH_INTERVAL:
            logger.debug("Touching backend: id=%s file chunk=%s bytes_downloaded=%s" % (id_, self._chunks, self._bytes_downloaded))
            # TODO: proper logging
            Backend.touch(id_)

    def file_exists_and_is_valid(self, local_file, md5, jid, tid):
        '''
        Validate that the give filepath exists on disk and its md5 matches that
        of the given one.  Return True if that's the case.
        '''
        self.log_msg(jid, tid, "Checking for existing file", local_file, log_level=logging.DEBUG)

        # check whether file exists
        if not os.path.exists(local_file):
            self.log_msg(jid, tid, "File does not exist", local_file, log_level=logging.DEBUG)
            return

        # Check whether the md5 matches
        local_md5 = common.generate_md5(local_file, base_64=True, poll_seconds=self._log_interval)
        if local_md5 != md5:
            self.log_msg(jid, tid, "Md5 mismatch (%s vs %s)" % (local_md5, md5),
                         local_file, log_level=logging.WARNING)
            return

        # Otherwise Return True to indicate that the file exists and matches the md5
        self.log_msg(jid, tid, "File already downloaded and verified.", local_file, log_level=logging.DEBUG)
        return True

    def cleanup_download(self, id_, jid, tid, destination, local_file):
        '''
        Cleanup the download.  This is currently a No-op, but serves as a 
        slot for any cleanup that may need to happen for the download
        before for the download worker process exits.
        '''
        message = "Cleaning up id %s" % id_
        self.log_msg(jid, tid, message, local_file, ljust=37, log_level=logging.INFO)


    def reset(self):
        '''
        Reset the state of the current file download
        '''
        self._chunks = 0
        self._bytes_downloaded = 0


    def log_msg(self, jid, tid, message, local_file, ljust=37, log_level=logging.INFO):
        '''
        Log a message about the given file.  This is a convenience function that 
        creates a message that is structured and consistent throughout the downloading
        processes. This makes readability easier when trolling through logs.
        
        example output:
            <jid>|<tid>  <message  <file path>
        
        '''
        msg_template = "%(jid)s|%(tid)s  %(message)s  %(filepath)s"
        logger.log(log_level, msg_template, {"message":message.ljust(ljust),
                                                              "jid":jid,
                                                              "tid":tid,
                                                              "filepath":local_file})

    def log_progress(self, local_file, jid, tid, file_size, log_level=logging.INFO):
        '''
        Log a message about the download progress of the given file. This uses
        the current state info (bytes_transferred) to calculate progress. 
        
        <jid>|<tid>  Downloading  <percentage>  <transferred/total>  <file path>
        
        example output:
        
            35748|000  Downloading   76%     859.38MB/1.09GB  /home/users/beanie/face.png

        '''
        progress = common.get_progress_percentage(self._bytes_downloaded, file_size)
        ratio_str = "%s/%s" % (common.get_human_bytes(self._bytes_downloaded),
                               common.get_human_bytes(file_size))

        msg = "Downloading  %s  %s" % (progress.rjust(4), ratio_str.rjust(18))
        self.log_msg(jid, tid, msg, local_file, log_level=log_level)


    def construct_result_dict(self, dl_info, id_, local_file, action, time_started, time_ended):
        '''
        Construct a result dictionary which contains the following keys:
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


class Backend:

    @classmethod
    @common.dec_retry(tries=3)
    def next(cls, account, project=None, location=None, number=1):
        """
        Return the next download (dict), or None if there isn't one.
        """
        path = "downloader/next"
        params = {"account": account, "project": project, "location": location}
        return Backend.get(path, params)

    @classmethod
    @common.dec_retry(tries=3)
    def touch(cls, id_, bytes_transferred=0):
        path = "downloader/touch/%s" % id_
        kwargs = {"bytes_transferred": bytes_transferred}
        return Backend.put(path, kwargs)

    @classmethod
    @common.dec_retry(tries=3)
    def finish(cls, id_, bytes_downloaded=0):
        path = "downloader/finish/%s" % id_
        payload = {"bytes_downloaded": bytes_downloaded}
        return Backend.put(path, payload)

    @classmethod
    @common.dec_retry(tries=3)
    def fail(cls, id_, bytes_downloaded=0):
        path = "downloader/fail/%s" % id_
        payload = {"bytes_downloaded": bytes_downloaded}
        return Backend.put(path, payload)

    @classmethod
    def get(cls, path, params):
        '''
        Return a list of items
        '''
        url = cls.make_url(path)
        headers = cls.make_headers()
        result = requests.get(url, params=params, headers=headers)
        result.raise_for_status()
        return result.json()

    @classmethod
    def put(cls, path, data):
        url = cls.make_url(path)
        headers = cls.make_headers()
        result = requests.put(url, headers=headers, data=data)
        result.raise_for_status()
        return result.json()

    @classmethod
    def post(cls, path, data):
        url = cls.make_url(path)
        headers = cls.make_headers()
        result = requests.post(url, headers=headers, data=data)
        result.raise_for_status()
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
        return {"accept-version": "v1",
                "authorization": "Token %s" % token}


class Downloader(object):
    """
    Downloader control object

    This class maintains the process worker "pool" and the shared state object.
    
     This queue may be
        to print out download history to the shell.    
    
    """
    RESULTS_MAX = 100

    def __init__(self, args):

        # Contains the user-provided arguments
        self.args = args

        # a list of all worker processes
        self._workers = []

        # a process-safe object to communicate the state of the downloader across processes
        self._run_state = multiprocessing.Array('c', "stoppingorstuff")

        # Initialize the state of download to "running"
        self._run_state.value = "running"

        # Create a results queue that will hold the results of all files
        # that are downloaded from each DownloadWorker
        self._results_queue = multiprocessing.Queue(self.RESULTS_MAX)

        # Record the start time of instantiation, so that we can report uptime
        self._start_time = time.time()

        # Register the SIGINT signal with our sigint handler
        signal.signal(signal.SIGINT, self.sigint_handler)

    def run(self):
        self.start_daemon()

    def start_daemon(self):
        """
        Initialize the process 'pool'.
        """
        self._start_time = time.time()
        logger.info("starting downloader daemon")
        self.init_workers()
        [wrk.start() for wrk in self._workers]

        # Join the workers. It's generally good practice to do this. Otherwise the
        # parent process can exit (and return control back to shell) before
        # the child processes exit (creating zombie processes).
        # see here: https://docs.python.org/2/library/multiprocessing.html#all-platforms
        [wrk.join() for wrk in self._workers]


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
        account = CONFIG.get("account") or None
        logger.info("account: %s", account)

        project = self.args.get("project") or None
        logger.info("project: %s", project)

        location = self.args.get("location") or None
        logger.info("location: %s", location)

        output_dir = self.args.get("output") or ""
        logger.info("output_dir: %s", output_dir)

        thread_count = self.args.get("thread_count") or 5
        logger.info("thread_count: %s", thread_count)

        # add DownloadWorker processes.
        self._workers = [DownloadWorker(self._run_state,
                                        self._results_queue,
                                        account=account,
                                        output_dir=output_dir,
                                        project=project,
                                        location=location) for i in range(thread_count)]

        # Add a HistoryWorker for printing out the history of downloaded files
        self._workers.append(HistoryWorker(run_state=self._run_state,
                                           results_queue=self._results_queue,
                                           print_interval=10,
                                           history_max=self.RESULTS_MAX))



    def sigint_handler(self, sig, frm):
        logger.warning("ctrl-c exit...")
        self.stop()
        self.exit()


    def exit(self):
        '''
        Raise a DownloaderExit exception. This will exit the process.
        
        Log out the uptime of daemon processes
        '''
        self.log_uptime()
        raise DownloaderExit(0)

    def log_uptime(self):
        '''
        Return the amount of time that the uploader has been running, e.g "0:01:28"
        '''
        seconds = time.time() - self._start_time
        human_duration = common.get_human_duration(seconds)
        logger.info("Uptime: %s", human_duration)


class HistoryWorker(multiprocessing.Process):



    def __init__(self, run_state, results_queue, print_interval=10, history_max=0):
        self._run_state = run_state
        self._results_queue = results_queue
        self._history_max = history_max
        self._print_interval = print_interval
        self._last_history = None
        super(HistoryWorker, self).__init__()



    def run(self):
        '''
        Start and return a thread that is responsible for pinging the app for
        Downloads to download (and populating the queue)
        '''

        while self._run_state.value == "running":
            self.print_history()

    def print_history(self):
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
        while self._run_state.value == "running":
            try:
                # transfer/empty the results queue into the history list
                while not self._results_queue.empty():
                    results_list.append(self._results_queue.get_nowait())

                # slice the list to contain only the last x values
                results_list = results_list[-self._history_max:]

                # Print the history
                history_summary = self.construct_history_summary(results_list)

                # Only print the history if it is different from before
                if history_summary == self._last_history:
                    logger.info('##### DOWNLOAD HISTORY ##### [No changes]')
                else:
                    logger.info("%s\n", history_summary)
                    self._last_history = history_summary

            except:
                logger.exception("Failed to report Summary")

            time.sleep(self._print_interval)

    def construct_history_summary(self, results_list):
        '''
        
        '''
        title = " DOWNLOAD HISTORY %s " % (("(last %s files)" % self._history_max) if self._history_max else "")
        column_names = ["Completed at", "Download ID", "Job", "Task", "Size", "Action", "Duration", "Thread", "Filepath"]
        table = downloader2.HistoryTableStr(data=list(reversed(results_list)),
                                            column_names=column_names,
                                            title=title.center(100, "#"),
                                            footer="#"*180,
                                            upper_headers=True)

        return table.make_table_str()



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

    logger.debug('Downloader args: %s', args)
    downloader = Downloader(args)
    downloader.run()

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
                                     log_filepath=log_filepath)


