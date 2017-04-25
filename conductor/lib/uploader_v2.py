import json
import sys
import signal
import time
import imp
import logging
import multiprocessing
import os
import string

import requests

from conductor import CONFIG
from conductor.lib import common, loggeria
from conductor.lib.downloader import DecAuthorize, DecDownloaderRetry

try:
    imp.find_module('conductor')
except ImportError, error:
    sys.path.append(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(
                        os.path.abspath(__file__)))))

                    # Duration that workers sleep when there's no work to perform
WORKER_SLEEP_DURATION = 15

# The amount of bytes to transfer as a chunk
UPLOAD_CHUNK_SIZE = 1048576  # 1MB

# Maximum times that a file will be retried if errors occur when downloading
MAX_UPLOAD_RETRIES = 5

# The frequency (in seconds) for which the Touch thread should
# report progress of the file (outside of start/finish)
TOUCH_INTERVAL = 10

# Log format when not running in DEBUG mode
LOG_FORMATTER = logging.Formatter('%(asctime)s  %(message)s')

# Global run-state variable that decorators and other functions can use to
# know when they should exit
RUN_STATE = multiprocessing.Array('c', 'stoppingorstuff')

LOGGER = logging.getLogger(__name__)

class Uploader(object):
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
        LOGGER.info("starting uploader daemon")

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
        account = CONFIG.get("account") or None
        LOGGER.info("account: %s", account)

        project = self.args.get("project") or None
        LOGGER.info("project: %s", project)

        location = self.args.get("location") or None
        LOGGER.info("location: %s", location)

        thread_count = self.args.get("thread_count") or 1
        LOGGER.info("thread_count: %s", thread_count)

        #### CREATE WORKER PROCESSES ####
        workers = {}

        # Create DownloadWorker processes
        for _ in range(thread_count):

            # Create a process-safe run_state object for controlling process
            run_state = multiprocessing.Array('c', "stoppingorstuff")
            wrk = UploaderWorker(run_state,
                    account=account,
                    project=project,
                    location=location)
            workers[wrk] = run_state

        if start:
            for wrkr in workers:
                wrkr.start()

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


class UploaderWorker(multiprocessing.Process):
    """
    Worker process for uplpads.

    It's job is to periodically ask the server for an upload object:
        
        {u'account': u'testaccountdomain',
         u'bytes_transferred': 0,
         u'filepath': u'/home/tester/maya/projects/Samples/Nuke/Nuke/nuke_test/img/sword_gas-l.png',
         u'gcs_url': u'https://storage.googleapis.com/Testing-Scott/accounts/testaccountdomain/bd55f770c8e0566e272243d7555cf506?Expires=1495676505&GoogleAccessId=239744134952-1itjkr0cjbki5aicdoqka6u87tnc052i%40developer.gserviceaccount.com&Signature=mOqFkTRRoy4R0Cc4jDkNZ4pPKHb%2BM6J50GTsaKU7zO7Szb4Up8sYUh%2BUHd30i1iTjGv6M1jUjtTRJRHqdvRQFa6Gfihfvk6WzH%2BQ2rC%2F0FVQQJ%2FYgfX%2BBSOznFw%2FjaWjYIj3o9BFXAQNHMjLszbxspWoqiDvUrjNXyY9fCg3Pjq3DacPWdPTAWkqvaXelvkxNA1fSdnU4a%2Fp8XOXaEmz8eQvwZaQHfNsh%2FoUKEhpgxAXSPDHCQMFfzgZnCZyZG2%2BjmJE5XiTj50uiBdnA3lnXn3uMAwtXFBHKi9NL6HwtGFRZP3s7HyNZtSMKRtySfnogAuIj7G%2Fo489YbyA5zr8Gg%3D%3D',
         u'id': u'bd55f770c8e0566e272243d7555cf506',
         u'jid': None,
         u'location': None,
         u'md5': u'vVX3cMjgVm4nIkPXVVz1Bg==',
         u'priority': 1,
         u'status': None,
         u'total_size': 12934,
         u'ulid': u'5273391011463168'}

    It will then create an FileGenerator() object from the filepath, registering
    the self.event_handler() method as the callback to be fired for each chunk uploded
    to GCS.

    It knows how to handle success and failure events from the upload stream.

    On success, will will clean up any state and go back to asking for the next upload.
    """
    def __init__(self, run_state, account=None, location=None, project=None):
        super(UploaderWorker, self).__init__()
        self._run_state = run_state
        self.account = account
        self.location = location
        self.project = project

        self.reset()

    def run(self):
        # Set the run_state value to "running"
        self._run_state.value = Uploader.STATE_RUNNING

        while self._run_state.value == Uploader.STATE_RUNNING:
            try:
                self._run()
            except:
                LOGGER.exception("Preventing process from exiting due to Exception:\n")
                # wait a little to allow for exception recovery .
                # TODO:(lws) this may be totally stupid/unnecessary)
                self.wait()

        # call stop method to properly shutdown child processes, cleanup, etc
        self.stop()

        LOGGER.debug("Exiting process")

    def reset(self):
        self.current_upload = None
        self.fileobj = None
        self.upload_attempts = 0

    def _run(self):
        self.reset()

        self.current_upload = next_upload()

        if not self.current_upload:
            self.wait()
            return

        return handle_upload()

    def handle_upload(self):
        filepath = self.current_upload.get("filepath")
        try:
            self.fileobj = FileGenerator(filepath, event_handler=self.handle_upload_event)
        except UploaderMissingFile as e:
            print e
            return
        else:
            return self.put_upload()

    def put_upload(self):
        try:
            result = Backend.put_file(self.fileobj, self.current_upload["gcs_url"])
        except FilePutError as e:
            return self.handle_put_error(e)
        else:
            return

    def handle_finish(self, result):
        print "done", result
        return result

    def next_upload(self):
        try:
            uploads = Backend.next(self.account, location=self.location, project=self.project) or []
        except BackendDown as e:
            print e
            return
        except BackendError as e:
            print e
            return
        else:
            if uploads:
                # Return the one download in the list
                return uploads[0]

    def handle_upload_event(self, filegen):
        print "Upload Event: ", event
        if event == "progress":
            self.handle_put_progress(filegen)
        if event == "success":
            self.handle_put_success(filegen)
        return

    def handle_put_progress(self, filegen):
        # TODO: periodically update (touch) server
        print "bytes so-far: ", filegen._bytes_read

    def handle_put_success(self, filegen):
        # TODO: update server (finish)
        print "Done!"

    def handle_put_error(self, error):
        print error
        # TODO: handle different errors accordingly
        if self.upload_attempts < 3:
            self.upload_attempts += 1
            self.wait()
            self.put_upload()
        
        return


    def wait(self):
        '''
        sleep for WORKER_SLEEP_DURATION

        Instead of doing one long sleep call, we make a loop of many short sleep
        calls. This gives the opportunity to check the running state, and exit
        the sleep process if necessary.
        '''
        for _ in range(WORKER_SLEEP_DURATION):
            if self._run_state.value == Uploader.STATE_RUNNING:
                time.sleep(1)

    def stop(self):
        print "process shutdown complete"


class UploaderMissingFile(Exception):
    """A file is missing"""

class FilePutError(Exception):
    """Something happened during the put"""

class BackendDown(Exception):
    """Backend is down"""

class BackendError(Exception):
    """Something happened on the backend"""

class FileGenerator(object):
    """
    Since requests.put() can take a generator as the data param in order to allow
    for streaming uploads, this class can be used to create a generator from a filepath.
    Optionally, it can take a function/callable class instance as an event handler.
    The handler will be called when each chunk of the file is read.
    """
    def __init__(self, filepath, chunk_size=1024, event_handler=None):
        if not os.path.exists(filepath):
            raise UploaderMissingFile(filepath)
        self._chunk_size = chunk_size
        self._file = open(filepath, "rb")

        self._bytes_read = 0
        self._event_handler = event_handler

    def __iter__(self):
        return self

    def next(self):
        chunk = self._file.read(self._chunk_size)
        if len(chunk) == 0:
            self.stop_event()
            raise StopIteration()
        self._bytes_read += len(chunk)
        self.progress_event()
        return chunk

    def progress_event(self):
        self._event_handler(self, event="progress")

    def stop_event(self):
        self._event_handler(self, event="success")


class Backend:
    headers = {"accept-version": "v1"}

    @classmethod
    def put_file(cls, filegen, signed_url):
        headers = {"Content-Type": "application/octet-stream"}
        try:
            resp = requests.put(signed_url, headers=headers, data=filegen)
        except e:
            raise FilePutError(e)
        else:
            return resp

    @classmethod
    def next(cls, account, project=None, location=None, number=1):
        """
        Return the next download (dict), or None if there isn't one.
        """
        # path = "downloader/next"
        # params = {"account": account, "project": project, "location": location}
        # return Backend.get(path, params, headers=cls.headers)

        strr = "[{\"ulid\":\"5273391011463168\",\"total_size\":12934,\"status\":null,\"priority\":1,\"md5\":\"vVX3cMjgVm4nIkPXVVz1Bg==\",\"location\":null,\"jid\":null,\"id\":\"bd55f770c8e0566e272243d7555cf506\",\"gcs_url\":\"https://storage.googleapis.com/Testing-Scott/accounts/testaccountdomain/bd55f770c8e0566e272243d7555cf506?Expires=1495676505&GoogleAccessId=239744134952-1itjkr0cjbki5aicdoqka6u87tnc052i%40developer.gserviceaccount.com&Signature=mOqFkTRRoy4R0Cc4jDkNZ4pPKHb%2BM6J50GTsaKU7zO7Szb4Up8sYUh%2BUHd30i1iTjGv6M1jUjtTRJRHqdvRQFa6Gfihfvk6WzH%2BQ2rC%2F0FVQQJ%2FYgfX%2BBSOznFw%2FjaWjYIj3o9BFXAQNHMjLszbxspWoqiDvUrjNXyY9fCg3Pjq3DacPWdPTAWkqvaXelvkxNA1fSdnU4a%2Fp8XOXaEmz8eQvwZaQHfNsh%2FoUKEhpgxAXSPDHCQMFfzgZnCZyZG2%2BjmJE5XiTj50uiBdnA3lnXn3uMAwtXFBHKi9NL6HwtGFRZP3s7HyNZtSMKRtySfnogAuIj7G%2Fo489YbyA5zr8Gg%3D%3D\",\"filepath\":\"/home/tester/maya/projects/Samples/Nuke/Nuke/nuke_test/img/sword_gas-l.png\",\"bytes_transferred\":0,\"account\":\"testaccountdomain\"}]"
        return json.loads(strr)

    @classmethod
    @common.dec_timer_exit(log_level=logging.DEBUG)
    def touch(cls, id_, bytes_transferred=0, account=None, location=None, project=None):
        path = "downloader/touch/%s" % id_
        kwargs = {"bytes_transferred": bytes_transferred,
                "account": account,
                "location": location,
                "project": project}
        try:
            return Backend.put(path, kwargs, headers=cls.headers)
        except requests.HTTPError as e:
            if e.response.status_code == 410:
                LOGGER.warning("Cannot Touch file %s.  Already finished (not active) (410)", id_)
                return
        raise

    @classmethod
    @common.dec_timer_exit(log_level=logging.DEBUG)
    def finish(cls, id_, bytes_downloaded=0, account=None, location=None, project=None):
        path = "downloader/finish/%s" % id_
        LOGGER.debug(path)
        payload = {"bytes_downloaded": bytes_downloaded,
                "account": account,
                "location": location,
                "project": project}
        try:
            return Backend.put(path, payload, headers=cls.headers)
        except requests.HTTPError as e:
            if e.response.status_code == 410:
                LOGGER.warning("Cannot finish file %s.  File not active (410)", id_)
                return
        raise

    @classmethod
    @common.dec_timer_exit(log_level=logging.DEBUG)
    def fail(cls, id_, bytes_downloaded=0, account=None, location=None, project=None):
        path = "downloader/fail/%s" % id_
        payload = {"bytes_downloaded": bytes_downloaded,
                "account": account,
                "location": location,
                "project": project}
        try:
            return Backend.put(path, payload, headers=cls.headers)
        except requests.HTTPError as e:
            if e.response.status_code == 410:
                LOGGER.warning("Cannot fail file %s.  File not active (410)", id_)
                return
        raise

    @classmethod
    @common.dec_timer_exit(log_level=logging.DEBUG)
    def bearer_token(cls, token):
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
        if path == "bearer":
            config_url = CONFIG.get("url", CONFIG["base_url"])
            return "%s/api/oauth_jwt?scope=user" % config_url

        ip_map = {
                "fiery-celerity-88718.appspot.com": "https://beta-api.conductorio.com",
                "eloquent-vector-104019.appspot.com": "https://dev-api.conductorio.com",
                "atomic-light-001.appspot.com": "https://api.conductorio.com"
                }
        config_url = CONFIG.get("url", CONFIG["base_url"]).split("//")[-1]
        project_url = string.join(config_url.split("-")[-3:], "-")
        if os.environ.get("LOCAL"):
            url_base = "http://localhost:8081"
        else:
            url_base = ip_map[project_url]
        url = "%s/api/v1/fileio/%s" % (url_base, path)
        return url
