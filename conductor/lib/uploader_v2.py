"""
Uploader daemon v2
"""
import base64
import datetime
import hashlib
import imp
import json
import logging
import multiprocessing
import os
import signal
import sys
import time

import requests

from conductor import CONFIG
from conductor.lib import common, loggeria
from conductor.lib.downloader import DecAuthorize  # , DecDownloaderRetry
from conductor.lib.downloader import HistoryWorker

try:
    imp.find_module('conductor')
except ImportError:  # , error:
    sys.path.append(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Duration that workers sleep when there's no work to perform
WORKER_SLEEP_DURATION = 15

# Time between updates to server.
WORKER_TOUCH_INTERVAL = 60  # seconds

# The amount of bytes to transfer as a chunk
UPLOAD_CHUNK_SIZE = 1048576  # 1MB

# Maximum times that a file will be retried if errors occur when downloading
MAX_UPLOAD_RETRIES = 5

# The frequency (in seconds) for which the Touch thread should
# report progress of the file (outside of start/finish)
TOUCH_INTERVAL = 60

# Log format when not running in DEBUG mode
LOG_FORMATTER = logging.Formatter('%(asctime)s  %(message)s')

# Global run-state variable that decorators and other functions can use to
# know when they should exit
RUN_STATE = multiprocessing.Array('c', 'stoppingorstuff')

LOGGER = logging.getLogger(__name__)


class Uploader(object):
    """
    Main Uploader process.

    - Launch workers
    - keep run states etc.
    """
    STATE_RUNNING = "running"
    STATE_STOPPING = "stopping"

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
        LOGGER.info("starting uploader daemon")

        global RUN_STATE
        RUN_STATE.value = self.STATE_RUNNING

        # Record the start time of instantiation, so that we can report uptime
        self._start_time = time.time()

        # Create and start all workers
        self._workers = self._create_workers(start=True)
        LOGGER.debug("Started workers:\n\t%s",
                     "\n\t".join(sorted([w.name for w in self._workers])))

    def stop_daemon(self):
        """
        Stop the downloader daemon and exit the application.

        1. change the run_state value of each worker's shared object value.
           This will trigger each worker's stop/cleanup behaviors.
        2. Exit the application runtime by raising an exception (we must break
           out of the join that occurred in the start_daemon method).
        """

        # Cycle through each worker, and change the share object's state
        # value to "stopping
        for worker, run_state in self._workers.iteritems():
            LOGGER.debug("changing %s from %s to %s", worker.name,
                         run_state.value, self.STATE_STOPPING)
            run_state.value = self.STATE_STOPPING

        # Join the workers. It's generally good practice to do this.
        # Otherwise the parent process can exit (and return control
        # back to shell) before the child processes exit (creating
        # zombie processes). see here:
        # https://docs.python.org/2/library/multiprocessing.html#all-platforms
        for wrk in self._workers:
            wrk.join()

        LOGGER.debug("All procs exited:\n\t%s",
                     "\n\t".join(sorted([w.name for w in self._workers])))

        # Log out the uptime of the daemon
        self.log_uptime()

    def _create_workers(self, start=True):
        """
        Create child worker processes.  For each worker, create a
        process/thread safe object that is used to communicate between
        this parent process and the worker.  Return a dictionary where
        the key is the process object, and the value its corresponding
        run_state state object.

        WORKERS:
            - DownloadWorker # Downloads files
            - HistoryWorker  # logs out history of downloaded files
        """
        account = CONFIG.get("account") or None
        LOGGER.info("account: %s", account)

        project = self.args.get("project") or None
        LOGGER.info("project: %s", project)

        location = self.args.get("location") or None
        LOGGER.info("location: %s", location)

        thread_count = self.args.get("thread_count") or 1
        LOGGER.info("thread_count: %s", thread_count)

        # CREATE WORKER PROCESSES
        workers = {}

        # Create DownloadWorker processes
        for _ in range(thread_count):

            # Create a process-safe run_state object for controlling process
            # run_state = multiprocessing.Array('c', "stoppingorstuff")
            global RUN_STATE
            wrk = UploaderWorker(
                RUN_STATE,
                self._results_queue,
                account=account,
                project=project,
                location=location)
            workers[wrk] = RUN_STATE

        log_history_wrk = self.create_log_history()

        workers[log_history_wrk] = RUN_STATE

        if start:
            for wrkr in workers:
                wrkr.start()

        return workers

    def create_log_history(self):
        # run_state = multiprocessing.Array('c', "stoppingorstuff")
        column_names = [
            "Completed at", "Upload ID", "Size", "Action", "Duration",
            "Thread", "Filepath"
        ]

        global RUN_STATE
        worker = HistoryWorker(
            run_state=RUN_STATE,
            results_queue=self._results_queue,
            print_interval=10,
            history_max=self.RESULTS_MAX,
            worker_type='upload',
            column_names=column_names)
        return worker

    def sigint_handler(self, sig, frm):
        '''
        Handles the SIGINT signal (i.e. the KeyboardInterrupt
        python exception).

        This simply calls the Downloader's stop_daemon method.

        Note that when registering this function as the signint handler,
        this function gets called by ALL child processes as well.  Because
        of this, we check which process is calling it, and only execute it
        if it's the main (parent) process.
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
        Return the amount of time that the uploader has been running,
        e.g "0:01:28"
        '''
        seconds = time.time() - self._start_time
        human_duration = common.get_human_duration(seconds)
        LOGGER.info("Uptime: %s", human_duration)


class UploaderWorker(multiprocessing.Process):
    """
    Worker process for uplpads.

    It's job is to periodically ask the server for an upload object:

        {u'account': u'testaccountdomain',
         u'bytes_transferred': 0,
         u'filepath': u'/home/testers/Nuke/Nuke/nuke_test/img/sword_gas-l.png',
         u'filesize': 1234,
         u'gcs_url': u'https://storage.googleapis.com/..snip..",
         u'id': u'bd55f770c8e0566e272243d7555cf506',
         u'jid': None,
         u'location': None,
         u'md5': u'vVX3cMjgVm4nIkPXVVz1Bg==',
         u'priority': 1,
         u'status': None,
         u'total_size': 12934,
         u'ulid': u'5273391011463168'}

    It will then create an FileGenerator() object from the filepath,
    registering the self.event_handler() method as the callback to be
    fired for each chunk uploded to GCS.

    It knows how to handle success and failure events from the upload stream.

    On success, will will clean up any state and go back to asking for the
    next upload.
    """

    def __init__(self,
                 run_state,
                 results_queue,
                 account=None,
                 location=None,
                 project=None):
        super(UploaderWorker, self).__init__()
        self._run_state = run_state
        self.account = account
        self.location = location
        self.project = project

        self.current_upload = None
        self.fileobj = None
        self.upload_attempts = 0
        self.last_touch = None
        self._results_queue = results_queue

    def run(self):
        # Set the run_state value to "running"
        self._run_state.value = Uploader.STATE_RUNNING

        while self._run_state.value == Uploader.STATE_RUNNING:
            try:
                self._run()
            except:
                LOGGER.exception(
                    "Preventing process from exiting due to Exception:\n")
                # wait a little to allow for exception recovery .
                # TODO:(lws) this may be totally stupid/unnecessary)
                self.reset()
                self.wait()

        # call stop method to properly shutdown child processes, cleanup, etc
        self.stop()

        LOGGER.debug("Exiting process")

    def reset(self):
        """
        Reset state
        """
        self.current_upload = None
        self.fileobj = None
        self.upload_attempts = 0
        self.upload_attempts = 0
        self.last_touch = None

    def _run(self):
        self.reset()

        self.current_upload = self.next_upload()

        if not self.current_upload:
            self.wait()
            return

        return self.handle_upload()

    def handle_upload(self):
        """
        Process an upload json object
        """
        try:
            self.fileobj = FileGenerator(
                self.current_upload, event_handler=self.handle_upload_event)
            return self.maybe_upload()

        except UploaderMissingFile as err:
            LOGGER.warning("local file missing: %s",
                           self.current_upload["filepath"])
            if not self.current_upload.get("id"):
                Backend.fail_unsigned(self.current_upload, location=self.location)
            else:
                Backend.fail(self.current_upload, bytes_downloaded=0, location=self.location)
            return

        except UploaderFileModified as err:
            LOGGER.warning("local file has changed: %s", err)
            Backend.fail(self.current_upload, bytes_downloaded=0, location=self.location)
            return

    def maybe_upload(self):
        '''
        Upload a file if md5 matches expectation.
        '''
        filepath = self.current_upload["filepath"]
        # expected_filesize = self.current_upload.get("filesize")
        origingal_md5 = self.current_upload.get("md5")
        expected_md5 = self.md5_for_current_upload()

        if expected_md5 == "skip":
            return

        if origingal_md5:
            local_md5 = self.file_md5(filepath)
        else:
            local_md5 = self.current_upload["md5"]
        if local_md5 != expected_md5:
            # error
            raise UploaderFileModified("different md5 - local: %s expected: %s"
                                       % (local_md5, expected_md5))

        # print meh
        return self.put_upload()

    def md5_for_current_upload(self):
        md5 = self.current_upload.get("md5")
        if md5:
            return md5
        self.current_upload["md5"] = self.file_md5(self.current_upload["filepath"])
        sign_result = Backend.sign(self.current_upload, location=self.location)
        if sign_result == "skip":
            return sign_result
        else:
            self.current_upload["gcs_id"] = sign_result["gcs_id"]
            self.current_upload["gcs_url"] = sign_result["gcs_url"]
            return self.current_upload["md5"]

    def file_md5(self, filepath):
        '''
        make an md5 sum of a file.
        '''
        chunk_size = 2**20
        md5 = hashlib.md5()
        with open(filepath, "rb") as fileobj:
            while True:
                chunk = fileobj.read(chunk_size)
                if not chunk:
                    break
                md5.update(chunk)
                if self.maybe_touch():
                    self.touch()
                    Backend.touch(
                        self.current_upload,
                        bytes_downloaded=0,
                        location=self.location
                    )
        digest = md5.digest()
        return base64.b64encode(digest)


    def put_upload(self):
        """
        Put the upload into GCS
        """
        # print "starting upload...", self.current_upload['filepath']
        self.touch()
        try:
            Backend.put_file(self.fileobj, self.current_upload["gcs_url"])
        except FilePutError as err:
            self.handle_put_error(err, self.fileobj)
            raise
        else:
            # print result
            return

    def handle_finish(self, result):
        """
        Callback for finish/success
        """
        # print "done", result
        self.reset()
        return result

    def next_upload(self):
        """
        Get the next upload
        """
        # print "fetching upload..."
        try:
            uploads = Backend.next(
                self.account, location=self.location,
                project=self.project) or []
        except BackendDown as err:
            # print err
            raise err
        except BackendError as err:
            # print err
            raise err
        else:
            if uploads:
                # Return the one download in the list
                return uploads[0]

    def handle_upload_event(self, filegen, event):
        """
        Callback for uploads
        """
        # print "Upload Event: ", event

        if self._run_state.value == Uploader.STATE_RUNNING:
            if event == "progress":
                self.handle_put_progress(filegen)
            if event == "success":
                self.handle_put_success(filegen)
        else:
            raise StopIteration()
        return

    def handle_put_progress(self, filegen):
        """
        Callback for upload progress
        """
        # print "bytes so-far: ", filegen.bytes_read

        if self.maybe_touch():
            self.touch()
            Backend.touch(
                self.current_upload,
                bytes_downloaded=filegen.bytes_read,
                location=self.location
            )
        else:
            return

    def handle_put_success(self, filegen):
        """
        Callback for finish/success
        """
        xferd = filegen.bytes_read \
            if filegen \
            else self.current_upload["bytes_transferred"]
        self.touch()
        Backend.finish(
            self.current_upload,
            bytes_downloaded=xferd,
            location=self.location
        )

        result = self._construct_result_dict(self.fileobj, "UL")
        self._results_queue.put_nowait(result)
        self.reset()
        # print "Done!"

    def handle_put_error(self, err, fileobj):
        """
        Callback for upload error
        """
        # print err
        # TODO: handle different errors accordingly
        if self.upload_attempts < 3:
            self.upload_attempts += 1
            self.wait()
            self.put_upload()

        result = self._construct_result_dict(fileobj, "Failed")
        self._results_queue.put_nowait(result)
        return

    def _construct_result_dict(self, filegen, action):
        '''
        Construct a "result" dictionary that contains information about how the
        download was handled.
        '''
        time_ended = time.time()
        result = {}
        result["ID"] = filegen.upload_file.get("id")
        result["Upload ID"] = filegen.upload_file.get("id")
        result["Size"] = filegen.upload_file.get("filesize")
        result["Filepath"] = filegen.upload_file.get("filepath")
        result["Action"] = action
        result["Started at"] = filegen.time_started
        result["Completed at"] = time_ended
        result["Duration"] = time_ended - filegen.time_started
        result["Thread"] = self.name
        return result

    def touch(self):
        self.last_touch = datetime.datetime.now()
        return

    def maybe_touch(self):
        if not self.last_touch:
            return True
        touch_delta = datetime.datetime.now() - self.last_touch
        return touch_delta.total_seconds > WORKER_TOUCH_INTERVAL

    def wait(self):
        '''
        sleep for WORKER_SLEEP_DURATION

        Instead of doing one long sleep call, we make a loop of many
        short sleep calls. This gives the opportunity to check the
        running state, and exit the sleep process if necessary.
        '''
        for _ in range(WORKER_SLEEP_DURATION):
            if self._run_state.value == Uploader.STATE_RUNNING:
                time.sleep(1)

    def stop(self):
        """
        Call at the end of shutdown
        """
        # print "process shutdown complete"


class UploaderMissingFile(Exception):
    """A file is missing"""


class UploaderFileModified(Exception):
    """something wring with local file"""


class FilePutError(Exception):
    """Something happened during the put"""


class BackendDown(Exception):
    """Backend is down"""


class BackendError(Exception):
    """Something happened on the backend"""


class FileGenerator(object):
    """
    Since requests.put() can take a generator as the data param in order to
    allow for streaming uploads, this class can be used to create a generator
    from a filepath. Optionally, it can take a function/callable class
    instance as an event handler. The handler will be called when each chunk
    of the file is read.
    """

    def __init__(self, upload_file, chunk_size=1024 * 1024,
                 event_handler=None):
        self.upload_file = upload_file
        filepath = self.upload_file.get("filepath")
        if not os.path.exists(filepath):
            raise UploaderMissingFile(filepath)
        self._chunk_size = chunk_size
        self._file = open(filepath, "rb")

        self.bytes_read = 0
        self._event_handler = event_handler
        self.time_started = time.time()

    def __iter__(self):
        return self

    def next(self):
        """
        Generator implementation
        """
        chunk = self._file.read(self._chunk_size)
        self.bytes_read += len(chunk)
        if len(chunk) == 0:
            self.stop_event()
            raise StopIteration()
        self.progress_event()
        return chunk

    def progress_event(self):
        """
        Fire callback
        """
        self._event_handler(self, event="progress")

    def stop_event(self):
        """
        Fire callback
        """
        self._event_handler(self, event="success")


class Backend:
    """
    Interface to backend (FileIO service)
    """
    headers = {"accept-version": "v1"}

    @classmethod
    def put_file(cls, filegen, signed_url):
        """
        Upload a file (streaming) into GCS
        """
        headers = {"Content-Type": "application/octet-stream"}
        try:
            resp = requests.put(signed_url, headers=headers, data=filegen)
        except Exception as err:
            raise FilePutError(err)
        else:
            return resp

    @classmethod
    def sign(cls, upload, location=None):
        """
        Sign an upload payload
        """
        path = "uploader/sign/%s" % upload["id"]
        kwargs = {
            "md5": upload["md5"],
            "location": location
        }
        try:
            return Backend.put(path, kwargs, headers=cls.headers)
        except requests.HTTPError as err:
            if err.response.status_code == 410:
                LOGGER.warning("Cannot Touch file %s.  Already finished \
                    (not active) (410)", upload["id"])
            raise err
        raise

    @classmethod
    def next(cls, account, project=None, location=None, number=1):
        """
        Return the next download (dict), or None if there isn't one.
        """
        path = "uploader/next"
        params = {"account": account, "project": project, "location": location}
        try:
            return Backend.get(path, params, headers=cls.headers)
        except requests.HTTPError as err:
            if err.response.status_code == 410:
                LOGGER.warning("Cannot Touch file %s.  Already finished \
                    (not active) (410)", upload["id"])
            raise err
        raise

    @classmethod
    def touch(cls, upload, location=None, bytes_downloaded=0):
        """
        Update backend with upload status
        """
        path = "uploader/touch/%s" % upload["id"]
        kwargs = {
            "bytes_transferred": bytes_downloaded,
            "location": location
        }
        try:
            return Backend.put(path, kwargs, headers=cls.headers)
        except requests.HTTPError as err:
            if err.response.status_code == 410:
                LOGGER.warning("Cannot Touch file %s.  Already finished \
                    (not active) (410)", upload["id"])
            raise err
        raise

    @classmethod
    def finish(cls, upload, location=None, bytes_downloaded=0):
        """
        Tell backend about upload success
        """
        path = "uploader/finish/%s" % upload["id"]
        LOGGER.debug(path)
        payload = {
            "bytes_transferred": bytes_downloaded,
            "location": location
        }
        try:
            return Backend.put(path, payload, headers=cls.headers)
        except requests.HTTPError as err:
            if err.response.status_code == 410:
                LOGGER.warning("Cannot finish file %s.  File not active (410)",
                               upload["id"])
            raise err
        raise

    @classmethod
    def fail(cls, upload, location=None, bytes_downloaded=0):
        """
        Tell backend about upload failure
        """
        path = "uploader/fail/%s" % upload["id"]
        payload = {
            "bytes_transferred": bytes_downloaded,
            "location": location
        }
        try:
            return Backend.put(path, payload, headers=cls.headers)
        except requests.HTTPError as err:
            if err.response.status_code == 410:
                LOGGER.warning("Cannot fail file %s.  File not active (410)",
                               upload["id"])
            raise err
        raise

    @classmethod
    def fail_unsigned(cls, upload, location=None):
        """
        Tell backend about upload failure
        """
        path = "uploader/fail_unsigned/%s" % upload["ulid"]
        headers = {"Content-Type": "application/json"}
        headers.update(cls.headers)
        payload = {
            "upload_file": json.dumps(upload),
            "location": location
        }
        try:
            return Backend.put(path, payload, headers=headers)
        except requests.HTTPError as err:
            if err.response.status_code == 410:
                LOGGER.warning("Cannot fail file %s.  File not active (410)",
                               upload["id"])
            raise err
        raise

    @classmethod
    def bearer_token(cls, token):
        """
        Bearer

        # FIXME: still needed?
        """
        url = cls.make_url("bearer")
        headers = dict(cls.headers)
        headers.update({"authorization": "Token %s" % token})
        result = requests.get(url, headers=headers)
        result.raise_for_status()
        return result.json()["access_token"]

    @classmethod
    @DecAuthorize()
    def get(cls, path, params, headers):
        '''
        Return a list of items
        '''
        url = cls.make_url(path)
        # print "backend verb=GET url=%s" % (url)
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        resp = response.json()
        if response.status_code == 205:
            resp["exists"] = True
        return resp

    @classmethod
    @DecAuthorize()
    def put(cls, path, data, headers):
        """
        Call requests put
        """
        url = cls.make_url(path)
        response = requests.put(url, data=data, headers=headers)
        response.raise_for_status()
        resp = response.json()
        if response.status_code == 205:
            resp = "skip"
        return resp

    @classmethod
    @DecAuthorize()
    def post(cls, path, data, headers, json=False):
        """
        Call requests put
        """
        url = cls.make_url(path)
        if json:
            response =  requests.post(url, json=data, headers=headers)
        else:
            response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        resp = response.json()
        if response.status_code == 205:
            resp["exists"] = True
        return resp

    @staticmethod
    def make_url(path):
        '''
        TODO: get rid of this hardcoding!!!
        '''
        if path == "bearer":
            config_url = CONFIG.get("url", CONFIG["base_url"])
            return "%s/api/oauth_jwt?scope=user" % config_url

        url_base = CONFIG.get("api_url")
        url = "%s/api/v1/fileio/%s" % (url_base, path)
        return url



def set_logging(level=None, log_dirpath=None):
    '''
    Set logging level and path.
    '''
    log_filepath = None
    if log_dirpath:
        log_filepath = os.path.join(log_dirpath, "conductor_ul_log")
    loggeria.setup_conductor_logging(
        logger_level=level,
        console_formatter=LOG_FORMATTER,
        file_formatter=LOG_FORMATTER,
        log_filepath=log_filepath)


def run_uploader(args):
    '''
    Start the uploader process. This process will run indefinitely, polling
    the Conductor cloud app for files that need to be uploaded.
    '''
    # convert the Namespace object to a dictionary
    args_dict = vars(args)

    # Set up logging
    log_level_name = args_dict.get("log_level") or CONFIG.get("log_level")
    log_level = loggeria.LEVEL_MAP.get(log_level_name)
    log_dirpath = args_dict.get("log_dir") or CONFIG.get("log_dir")
    set_logging(log_level, log_dirpath)

    LOGGER.debug('Uploader parsed_args is %s', args_dict)
    resolved_args = resolve_args(args_dict)
    uploader = Uploader(resolved_args)
    uploader.start_daemon()


def resolve_args(args):
    '''
    Resolve all arguments, reconsiling differences between command line args
    and config.yml args.  See resolve_arg function.
    '''
    args["md5_caching"] = resolve_arg("md5_caching", args, CONFIG)
    args["database_filepath"] = resolve_arg("database_filepath", args, CONFIG)
    args["location"] = resolve_arg("location", args, CONFIG)

    return args


def resolve_arg(arg_name, args, config):
    '''
    Helper function to resolve the value of an argument.
    The order of resolution is:
    1. Check whether the user explicitly specified the argument when calling/
       instantiating the class. If so, then use it, otherwise...
    2. Attempt to read it from the config.yml. Note that the config also
       queries environment variables to populate itself with values.
       If the value is in the config then use it, otherwise...
    3. return None

    '''
    # Attempt to read the value from the args
    value = args.get(arg_name)
    # If the arg is not None, it indicates that the arg was explicity
    # specified by the caller/user, and it's value should be used
    if value is not None:
        return value
    # Otherwise use the value in the config if it's there,
    # otherwise default to None
    return config.get(arg_name)
