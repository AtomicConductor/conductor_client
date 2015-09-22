#!/usr/bin/env python

import os, re, ast, io
import multiprocessing
from Queue import Queue
import subprocess
import urllib2
import base64
import json
import time
import string
import hashlib
import startup_lib
import threading
import traceback
import Queue
import logging
import random
from functools import wraps


from apiclient import discovery
from apiclient.http import MediaIoBaseDownload
from oauth2client.client import GoogleCredentials

CHUNKSIZE = 1024 * 1024  # 1MB
credentials = GoogleCredentials.get_application_default()
storage = discovery.build('storage', 'v1', credentials=credentials)


logger = logging.getLogger('upload_node_main')
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)8s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)



def dec_retry(RetryExceptions, tries=8, logger=logger):
    '''
    Retry calling the decorated function using an exponential backoff.

    RetryExceptions: An Exception class (or a tuple of Exception classes) that
                    this decorator will catch/retry.  All other exceptions that
                    occur will NOT be retried.

    tries: int. number of times to try (not retry) before raising

    This retry function not only incorporates exponential backoff, but also
    "jitter".  see http://www.awsarchitectureblog.com/2015/03/backoff.html.
    Instead of merely increasing the backoff time exponentially (determininstically),
    there is a randomness added that will set the sleeptim anywhere between
    0 and the full exponential backoff time length.

    '''
    def retry_decorator(f):

        @wraps(f)
        def retry_(*args, **kwargs):
            for try_num in range(1, tries + 1):
                try:
                    return f(*args, **kwargs)
                except RetryExceptions, e:
                    # use random for jitter.
                    sleep_time = random.randrange(0, 2 ** try_num)
                    msg = "%s, Retrying in %d seconds..." % (str(e), sleep_time)
                    logger.warning(msg)
                    time.sleep(sleep_time)
            return f(*args, **kwargs)
        return retry_
    return retry_decorator

def dec_function_timer(func):
    '''
    DECORATOR
    Wraps the decorated function/method so that when the function completes, it
    will print out the time that it took (in seconds) to complete.
    '''
    @wraps(func)
    def wrapper(*a, **kw):
        func_name = getattr(func, "__name__", "<Unknown function>")
        start_time = time.time()
        result = func(*a, **kw)
        finish_time = '%s :%.2f seconds' % (func_name, time.time() - start_time)
        logger.info(finish_time)
        return result
    return wrapper


class Uploader(startup_lib.StartupScript):
    """ Script to run on instances to perform renders.
        Inherited class attributes are
            self.logger
            self.account
            self.metadata
            self.tags
    """

    def __init__(self, logger):
        super(Uploader, self).__init__(logger)
        self.logger = logger
        self.logger.debug('Running Uploader')
        self.run()
        self.logger.debug('Exiting Uploader')


    def run(self):
        self.start_machine()
        self.setup_generic_environment()
        self.run_uploader_loop()
        self.stop_machine()



    def get_upload_files(self):
        """Retrieve the command to run from the metadata on the node.
        Returns a cloud storage path to the upload file
        """
        self.logger.debug('getting upload files')
        start_dict = {'instance':startup_lib.hostname}
        request = urllib2.Request("%s/uploads/server/next" % self.conductor_url)
        base64string = base64.encodestring(
            '%s:%s' % (startup_lib.username, startup_lib.password)).replace('\n', '')
        request.add_header("Authorization", "Basic %s" % base64string)
        request.add_header('Content-Type', 'application/json')
        request.get_method = lambda: 'PUT'
        print 'start_dict is \n%s' % start_dict
        print 'conductor url is: %s' % self.conductor_url
        try:
            response = urllib2.urlopen(request, json.dumps(start_dict))
        except urllib2.HTTPError, e:
            return None, None
        try:
            raw_data = response.read()
            self.logger.debug('raw response is: %s', raw_data)
            self.logger.debug('response.code is %s', response.code)
            data = json.loads(raw_data)
        except ValueError, e:
            self.logger.debug('could not decode json response from get_upload_files')
            self.logger.debug('response was %s', response)
            return None, None
        self.logger.debug('data is %s', data)
        upload_files = data['upload_files']
        upload_id = str(data['upload_id'])
        return upload_files, upload_id

    def get_hashstore_filepath(self, md5):
        '''
        For the given md5, return its gluster filepath
        '''
        hex_md5 = startup_lib.convert_base64_to_hex(md5)
        hashstore_filepath = "%s/accounts/%s/hashstore/%s" % (startup_lib.MASTER_MOUNT,
                                                              self.account,
                                                              hex_md5)
        return hashstore_filepath

    def do_thread_loop(self, queue, results_queue, thread_number, file_count):


        while True:  # This will exit when the file queue is empty
            try:
                filepath, gcs_md5 = queue.get(block=False)
            except Queue.Empty:
                self.logger.debug("[thread %s]Thread Queue Empty. Exiting thread", thread_number)
                return

            try:
                self.logger.debug('[thread %s]Addressing file:%s', thread_number, filepath)
                self.logger.debug('[thread %s]gcs md5: %s', thread_number, gcs_md5)

                hashstore_filepath = self.get_hashstore_filepath(gcs_md5)
                gcs_filepath = get_gcs_filepath(startup_lib.DEFAULT_BUCKET, self.account, gcs_md5)


                self.logger.debug("[thread %s]GCS filepath: %s", thread_number, gcs_filepath)
                self.logger.debug("[thread %s]Hashstore filepath: %s", thread_number, hashstore_filepath)
                result = download_gcs_file(gcs_filepath, gcs_md5, hashstore_filepath, logger=self.logger)


                # Change permissions on the file
                # TODO: do we really want to mark as executable? (though it's impossible to know if the file was originally executable when copied from client's machine, yah?)
                chmod_filepath_777(hashstore_filepath, logger=self.logger)

                # ## TODO: HACK! Parse the Maya ascii file and replace any Windows' drives with a gluster prefix
                if hashstore_filepath.endswith('.ma'):
                    self.logger.info('[thread %s]Hacking Maya ascii file to replace Windows lettered-drive paths', thread_number)
                    try:
                        ascii_hack_lettered_drives(hashstore_filepath, logger=self.logger)
                    except:
                        self.logger.error("[thread %s]Failed to hack lettered paths for file: %s", thread_number, hashstore_filepath)
                        raise
                    self.logger.debug('[thread %s]Maya ascii hack completed', thread_number)

                results_queue.put(result)
                queue.task_done()
                progress_percent = float(results_queue.qsize()) / file_count
                logger.info("JOB SYNC PROGRESSS: {0:.2f}%".format(progress_percent * 100))



            # TODO:(lws) This is here for safety/visibility.  Not sure if it's required or not.
            except Exception as e:
                self.logger.debug("[thread %s]******** ERROR ***************", thread_number)
                self.logger.debug("[thread %s]%s", thread_number, str(e))
                self.logger.debug("[thread %s]%s", thread_number, traceback.format_exc())
                self.logger.debug("[thread %s]********************************", thread_number)
                raise


    @dec_function_timer
    def run_uploads(self, upload_files):
        self.logger.debug('in run_uploads')
        upload_queue = Queue.Queue()
        results_queue = Queue.Queue()
        max_threads = multiprocessing.cpu_count() * 2
        threads = []

        self.logger.info("Syncing the following files:")
        for filename, md5 in upload_files.iteritems():
            self.logger.info("\t%s", filename)
            upload_queue.put((filename, md5))


        initial_thread_count = threading.active_count()
        self.logger.debug("Initial active thread count: %s", initial_thread_count)

        # Spawn as many threads as there are files (up to the max thread count)
        for thread_number in range(max_threads):
            thread = threading.Thread(target=self.do_thread_loop, args=(upload_queue, results_queue, thread_number, len(upload_files)))
            thread.setDaemon(True)  # TODO:Not sure if this is good or bad
            threads.append(thread)
            thread.start()


        self.logger.debug('Syncing threads launched')

        for thread_number, thread in enumerate(threads):
            self.logger.debug('waiting for thread: %s', thread_number)
            thread.join()

        logger.debug("Threads finished")

        logger.debug("Validating thread results")
        # Validate that the results of all of the threads
        invalid_filepaths = self.validate_results(upload_files, results_queue)
        if invalid_filepaths:
            # TODO:(lws) We should probbably catch this exception and retry the failed files.
            #            At the VERY LEAST, we should change the status of the upload job
            #            back to "server_pending".
            raise Exception("Files failed to synch:\n\t%s" % "\n\t".join(invalid_filepaths))

        logger.info("All files synched successfully")

        # Return the count of how many files actually got transferred.
        transfer_count = len([result for result in results_queue.queue if result[-1]])
        return transfer_count


    def validate_results(self, filepaths, results_queue):
        '''
        Validate that all of the files that the Upload job was supposed to sync
        have actually been synced.  This is achieved by comparing the original upload
        files list (filepaths) to the results file list (results_queue).
        '''
        # Create a dictionary that contains all of the files that were actually successfully synced/verified
        results_dict = {}

        for filepath, local_md5, gcs_md5, _ in results_queue.queue:
            results_dict[filepath] = {"local_md5":local_md5, "gcs_md5":gcs_md5}

        # Iterate through the original filepaths and check whether they:
        #   1. Exist in the results queue
        #   2. That their md5 matches the expected md5 (provided by the app/gcs)
        invalid_filepaths = []
        for filepath, md5 in filepaths.iteritems():
            hashstore_filepath = self.get_hashstore_filepath(md5)
            if hashstore_filepath not in results_dict or (results_dict[hashstore_filepath]["local_md5"] !=
                                                          results_dict[hashstore_filepath]["gcs_md5"]):

                invalid_filepaths.append(hashstore_filepath)

        return invalid_filepaths


    def complete_upload(self, upload_id):
        """Retrieve the command to run from the metadata on the node.
        """
        self.logger.debug('marking %s as complete...', upload_id)
        start_dict = {'upload_id':upload_id, 'status':'success'}
        request = urllib2.Request("%s/uploads/%s/finish" % (self.conductor_url, upload_id))
        base64string = base64.encodestring(
            '%s:%s' % (startup_lib.username, startup_lib.password)).replace('\n', '')
        request.add_header("Authorization", "Basic %s" % base64string)
        request.add_header('Content-Type', 'application/json')
        request.get_method = lambda: 'POST'
        try:
            response = urllib2.urlopen(request, json.dumps(start_dict))
        except urllib2.HTTPError, e:
            return None
        data = json.loads(response.read())
        self.logger.debug('marked %s as complete', upload_id)
        return str(data['status'])


    def run_uploader_loop(self):
        self.logger.debug('starting uploader loop...')
        while True:
            self.logger.info("Looking for work to do")
            upload_files, upload_id = self.get_upload_files()
            self.logger.debug("Call to fetch upload files complete")
            if not upload_files:
                # TODO: perhaps wait for runtime > 10mins
                self.logger.debug('no more files to upload. exiting...')
                break
            else:
                self.logger.debug("Running uploader for upload_id: %s", upload_id)
                self.logger.debug('%s files to sync...', len(upload_files))
                actual_transfer_count = self.run_uploads(upload_files)
                self.logger.debug("Upload/Syncing complete")
                self.complete_upload(upload_id)
                self.logger.info("  Upload Job Complete!  ".center(50, "#"))
                self.logger.info("Upload Job ID: %s", upload_id)
                self.logger.info("File count: %s", len(upload_files))
                self.logger.info("Files actually transferred: %s", actual_transfer_count)
                self.logger.info("#"*50)

        self.logger.debug('exited uploader loop')

    def start_machine(self):
        self.logger.debug('registering instance with app')

        request_endpoint = "%s/api/v1/instance/initupload" % self.conductor_url
        self.logger.debug('making request to: %s', request_endpoint)
        request = urllib2.Request(request_endpoint)

        base64string = base64.encodestring('%s:%s' % (startup_lib.username,
                                                      startup_lib.password)).replace('\n', '')

        request.add_header("Authorization", "Basic %s" % base64string)
        request.add_header('Content-Type', 'application/json')
        request.get_method = lambda: 'POST'

        start_dict = {'name':startup_lib.hostname,
                      'account':self.account}
        self.logger.debug('json data: %s', start_dict)


        max_attempts = 5
        attempts = 1
        while True:
            try:
                response = urllib2.urlopen(request, json.dumps(start_dict))
                break
            except urllib2.HTTPError, excep:
                self.logger.debug("Caught error during attempt %s: %s", attempts, excep)
                time.sleep(attempts)
                attempts += 1
                if attempts > max_attempts:
                    raise


        data = json.loads(response.read())
        self.logger.debug('instance registered')
        return data

    def stop_machine(self):
        if not self.auto_kill:
            self.logger.debug('not killing machine')
            return {}
        self.logger.debug('killing machine')

        stop_dict = {'instance':startup_lib.hostname, 'account':self.account}
        request = urllib2.Request("%s/api/v1/instance/stopmachine" % self.conductor_url)

        base64string = base64.encodestring('%s:%s' % (
            startup_lib.username,
            startup_lib.password)).replace('\n', '')

        request.add_header("Authorization", "Basic %s" % base64string)
        request.add_header('Content-Type', 'application/json')
        request.get_method = lambda: 'PUT'

        attempts = 1
        while attempts < 6:
            try:
                response = urllib2.urlopen(request, json.dumps(stop_dict))
                attempts = 7
            except urllib2.HTTPError, excep:
                self.logger.debug("Caught error, %s" % excep)
                time.sleep(attempts)
                attempts += 1

        data = json.loads(response.read())
        startup_lib.delete_instance(startup_lib.hostname, logger=self.logger)
        return data




@dec_retry(RetryExceptions=Exception)
def download_gcs_file(gcs_filepath, gcs_md5, local_filepath, force=False, logger=logger):
    '''
    Download the given gcs file to the given local filepath.
    This function handles many of errors/conditions that must be considered when
    doing any file copying operations (e.g. existence, permissions, integrity, etc)

    1. Check to see if the file already exists locally and if it matches
       the hash of the file in gcs. If we have a match already, then simply return.
    2. Create the local destination directory (including subdirectories).
    3. Download the file from gcs.
    4. Check the md5 hash of the downloaded file to ensure integrity

    '''
    #  If the local file already exists and is synced with GCS, then return
    if os.path.isfile(local_filepath):
        #  Get the local md5
        local_md5 = startup_lib.generate_md5(local_filepath)
        logger.debug('Local md5 is %s: %s', local_md5, local_filepath)
        logger.debug('gcs md5: %s', gcs_md5)
        # If the md5's match and we're not force syncing, then simply return
        if  bool(local_md5 == gcs_md5) and not force:
            logger.debug('File is synced. Skipping Transfer: %s', local_filepath)
            return (local_filepath, local_md5, gcs_md5, False)  # return False to indicate no actual transfer occured


    # Create the destination directory (including any subdirectories)
    local_dirpath = os.path.dirname(local_filepath)
    safe_mkdirs(local_dirpath)

    # Download the file
    bucket_root, gcs_object_path = split_gcs_filepath(gcs_filepath)
    logger.info("Downloading from gcs: %s", gcs_filepath)
    _download_gcs_file(bucket_root.lstrip("/"), gcs_object_path, local_filepath, logger=logger)

    # MD5-check the file to ensure it matches GCS
    local_md5 = startup_lib.generate_md5(local_filepath)
    if  local_md5 != gcs_md5:
        # TODO(lws): We might want to raise a custom exception, so that we can target it for Retries
        raise Exception("Failed post download hashcheck: %s", local_filepath)

    logger.info("Download success: %s", local_filepath)
    return (local_filepath, local_md5, gcs_md5, True)  # return True to indicate that an actual transfer occured


def chmod_filepath_777(filepath, logger=logger):
    '''
    Chmod the given filepath to permission of 777
    '''
    # TODO:(lws) Will we ever need to sudo this?
    logger.debug('chmoding 777 %s', filepath)
    os.chmod(filepath, 0777)  # note that python acknowledges the leading zeroand interprets it as an octal (and internally converts it to an int of 511)


def safe_mkdirs(dirpath):
    '''
    Create the given directory.  If it already exists, suppress the exception.
    This function is useful when handling concurrency issues where it's not
    possible to reliably check with a directory exists before creating it.
    '''
    try:
        os.makedirs(dirpath)
    except OSError:
        if not os.path.isdir(dirpath):
            raise


def _download_gcs_file(bucket_name, object_name, local_filepath, generation=None,
                       logger=None, chunksize=CHUNKSIZE):
    '''
    This is a base-level gcs downloader function. It's intentionally lite on
    error/condition checking.  Wrap this is in a higher-level function to
    add required functionality (such as directory existence/permissions, md5-check etc)
    '''
    # Instaniate a credentials instance. A new instance should be made for each thread
    # bc this instance is an argument th storage instance below, which too, must
    # be instantiated per thread.
    credentials = GoogleCredentials.get_application_default()
    # Generate a storage instance. Note that this object is not threadsafe and
    # therfore should instantiated each time (per thread).
    storage = discovery.build('storage', 'v1', credentials=credentials)
    request = storage.objects().get_media(bucket=bucket_name,
                                          object=object_name,
                                          generation=generation)


    logger.debug("Downloading to: %s", local_filepath)
    file_handler = io.FileIO(local_filepath, "w")

    downloader = MediaIoBaseDownload(file_handler, request, chunksize=chunksize)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            logger.debug(' %s%% %s', int(status.progress() * 100), local_filepath)
    logger.debug('Download Complete: %s', local_filepath)
    file_handler.close()
    return local_filepath


def get_gcs_filepath(bucket, account, md5):
    '''
    For the given md5, return it's gcs filepath
    '''
    gcs_filepath = "/%s/accounts/%s/hashstore/%s" % (bucket, account, md5)
    return gcs_filepath


def split_gcs_filepath(gcs_filepath):
    '''
    Split the gcs filepath, returning the bucket root and the relative gcs filepath

    Example:
        gcs_filepath: '/conductor/files/cat.jpg'
        return : ('/conductor', 'files/cat.jpg')
    '''
    assert gcs_filepath.startswith("/"), 'Given gcs filepath does not begin with expected root "/": %s' % gcs_filepath

    # Find the first forward slash (after the initial root )
    split_idx = gcs_filepath.find("/", 1)

    # If no other slash was found then simply return the original path as the bucket root, along with an empty string
    if split_idx == -1:
        return gcs_filepath, ""
    bucket_root = gcs_filepath[:split_idx]
    object_filepath = gcs_filepath[split_idx:].lstrip("/")
    return bucket_root, object_filepath


def ascii_hack_lettered_drives(filepath, logger=logger):
    '''
    HACK!!!
    Parse the given maya ascii file for any filepaths that reference
    a Window's lettered drive (e.g. Z:, y: etc ) and prefix them with the full
    gluster mount.  This operation can only be done on ascii maya file's (obviously).

    TODO:
    The reason this is being done is because even though we (conductor) can
    recreate Windows-looking paths on linux via symlinks e.g "z:/windows/cat.jpg",
    when maya attempts to read that path from disk, it's unable to find/register
    it.  This seems to be an issue specific to maya.  More research is needed
    in order to find a better solution (rather than hacking our client's maya
    asciii files!! :) )
    '''
    with open(filepath, 'r') as source_file:
        lines = source_file.readlines()

    # Rewrite the file with letter mapping resolved
    with open(filepath, 'w') as write_file:
        for line in lines:
            # cyle through each letter in the alphabet and prefix any references to a lettered drive with the glust path
            for letter in string.letters:
                lettered_drive = '%s:' % letter
                if '"%s/' % lettered_drive in line:
                    prefixed_line = '"/mnt/cndktr_glus/windows_%s/' % lettered_drive
                    logger.debug("Replacing line: %s", line.strip())
                    line = line.replace('"%s/' % lettered_drive, prefixed_line)
                    logger.debug("With this line: %s", line.strip())
            write_file.write(line)



if __name__ == "__main__":

    # Attempt to setup logging first so that we can record any issues immediately for debugging
    try:
        log_filepath = startup_lib.get_conductor_log_path(strict=True)
        logger = startup_lib.setup_logging(log_filepath)
    except:
        startup_lib.print_stderr('Failed to initialize logger')
        startup_lib.print_last_exception()
        # subprocess.call(['shutdown', '-h', 'now']) #TODO: This should probably be called in some clean way
        # Raise the exception to exit
        raise

    # Start the upload loop
    try:
        uploader = Uploader(logger)

    except:
        startup_lib.print_last_exception(logger)
        # Global fail safe to kill instance
        try:
            uploader.stop_machine()
        except:
            logger.debug('would be deleting instance')
            startup_lib.print_last_exception(logger)
            startup_lib.delete_instance(startup_lib.hostname, logger=logger)
    finally:
        if os.environ.get('AUTO_KILL'):
            logger.info("shutting down")
            subprocess.call(['shutdown', '-h', 'now'])
