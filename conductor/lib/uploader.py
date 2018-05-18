import datetime
import json
import logging
import os
import Queue
import re
import sys
import thread
import tarfile
from threading import Thread
import tempfile
import time
import traceback

from conductor import CONFIG
from conductor.lib import api_client, common, worker, client_db, loggeria

LOG_FORMATTER = logging.Formatter('%(asctime)s  %(name)s%(levelname)9s  %(threadName)s:  %(message)s')

logger = logging.getLogger(__name__)


class MD5Worker(worker.ThreadWorker):
    '''
    This worker will pull filenames from in_queue and compute it's base64 encoded
    md5, which will be added to out_queue
    '''

    def __init__(self, *args, **kwargs):
        # The location of the sqlite database. If None, it will degault to a value
        self.md5_caching = kwargs.get('md5_caching')
        self.database_filepath = kwargs.get('database_filepath')

        self.tar_size_threshold = kwargs.get('tar_size_threshold')
        self.tar_queue = kwargs.get('tar_queue')

        worker.ThreadWorker.__init__(self, *args, **kwargs)

    def do_work(self, job, thread_int):
        logger.debug('job is %s', job)
        filename, submission_time_md5 = job
        assert isinstance(filename, (str, unicode)), "Filepath not of expected type. Got %s" % type(filename)

        filename = str(filename)
        file_info = self.get_file_info(filename)
        current_md5 = file_info["md5"]
        # if a submission time md5 was provided then check against it
        if submission_time_md5:
            logger.info("Enforcing md5 match: %s for: %s", submission_time_md5, filename)
            if current_md5 != submission_time_md5:
                message = 'MD5 of %s has changed since submission\n' % filename
                message += 'submitted md5: %s\n' % submission_time_md5
                message += 'current md5:   %s\n' % current_md5
                message += 'This is likely due to the file being written to after the user submitted the job but before it got uploaded to conductor'
                logger.error(message)
                raise Exception(message)
        self.metric_store.set_dict('file_md5s', filename, current_md5)

        # If the file size is "small" then add it to the tar_queue
        if file_info["size"] < self.tar_size_threshold:
            logger.debug("small file: %s", filename)
            self.tar_queue.put_nowait(file_info)
            return

        return (filename, current_md5)

    def get_file_info(self, filepath):
        '''
        For the given filepath, return information about the file, e.g. 
        size, md5, modtime.

        Use the sqlite db cache to retrive this info, otherwise generate 
        the md5 from scratch and update the cache with  the new value(s).
        '''
        # Stat the file for basic file info
        file_info = get_file_info(filepath)

        # If md5 caching is disabled, then just generate the md5 from scratch
        if not self.md5_caching:
            md5 = common.generate_md5(filepath, base_64=True, poll_seconds=5)

        else:
            # attempt to retrieve cached file information
            file_cache = client_db.FilesDB.get_cached_file(file_info,
                                                           db_filepath=self.database_filepath,
                                                           thread_safe=True)

            # If there's a cache available, use the md5 value from it.
            if file_cache:
                md5 = file_cache["md5"]
            # Otherwise calculate the md5 from scratch.
            else:
                logger.debug("No md5 cache available for file: %s", filepath)
                md5 = common.generate_md5(filepath, base_64=True, poll_seconds=5)

        # inject the md5 into the file info, then update the cache in the db
        file_info["md5"] = md5
        self.cache_file_info(file_info)
        return file_info

    def cache_file_info(self, file_info):
        '''
        Store the given file_info into the database
        '''
        client_db.FilesDB.add_file(file_info,
                                   db_filepath=self.database_filepath,
                                   thread_safe=True)


class MD5OutputWorker(worker.ThreadWorker):
    '''
    This worker will batch the computed md5's into self.batch_size chunks.
    It will send a partial batch after waiting self.wait_time seconds
    '''

    # The maximum size that a tarball may be
    TARBALL_MAX_SIZE = 4000000000  # 4GB

    def __init__(self, *args, **kwargs):
        worker.ThreadWorker.__init__(self, *args, **kwargs)
        self.batch_size = 100  # the controlls the batch size for http get_signed_urls
        self.tar_queue = kwargs.get("tar_queue")
        self.wait_time = 1
        self.batch = {}

    def check_for_poison_pill(self, job):
        ''' we need to make sure we ship the last batch before we terminate '''
        if job == self.PoisonPill():
            logger.debug('md5outputworker got poison pill')
            self.ship_batch()
            self.mark_done()
            thread.exit()

    # helper function to ship batch
    def ship_batch(self):
        if self.batch:
            logger.debug('sending batch: %s', self.batch)
            self.put_job(self.batch)
            self.batch = {}

    def target(self, thread_int):

        while not common.SIGINT_EXIT:
            try:
                # block on the queue with a self.wait_time second timeout
                file_md5_tuple = self.in_queue.get(True, self.wait_time)

                self.check_for_poison_pill(file_md5_tuple)

                # add (filepath: md5) to the batch dict
                self.batch[file_md5_tuple[0]] = file_md5_tuple[1]

                # if the batch is self.batch_size, ship it
                if len(self.batch) == self.batch_size:
                    self.ship_batch()

            # This happens if no new messages are put into the queue after
            # waiting for self.wait_time seconds
            except Queue.Empty:
                self.ship_batch()
                continue
            except Exception:
                error_message = traceback.format_exc()
                self.error_queue.put(error_message)
                self.mark_done()

            # mark this task as done
            self.mark_done()

    def join(self):
        '''
        SUPER HACK to inject tar functionality into existing uploader mechanics with as little changes
        as possible. This is an embarrassment and should be refactored ASAP.

        Override the parent join method so that after all files in the input_queue have been processed
        we can then tar up all the small files that we bypassed (placed in the tar_queue).
        Once the tar file has been created, put it into the input_queue (so that it will be processed
        just like any other file). Then call the parent join method to resume the normal logic flow.
        '''
        # Wait until all the "normal" size files have finished processing
        self.in_queue.join()

        # Get all the "small" files that have been collected in the tar queue
        small_files = worker.empty_queue(self.tar_queue)

        # If there are any small files, tar them up and put them in the input_queue for uploading.
        if small_files:

            # check whether the size of all of the files is within the allowed limit
            total_size = sum((f["size"] for f in small_files))
            logger.debug("total tar files size: %s", common.get_human_bytes(total_size))
            if total_size > self.TARBALL_MAX_SIZE:
                raise Exception("Exceeded maximum tarball size of %s vs %s. Reduce tarball size by "
                                "reducing --tar_size_threshold value" % (common.get_human_bytes(self.TARBALL_MAX_SIZE),
                                                                         common.get_human_bytes(total_size)))

            # Cleanup any old temp files that may have been left
            # TODO:(lws) This is dangerous, temporary hack to make sure we don't leave huge temp files
            # laying around on customer machines.
            self.remove_temp_files()

            # Create a temporary tar file on disk and tar
            with tempfile.NamedTemporaryFile("w+b", prefix="conductor-tmp-", suffix=".tar", delete=False) as tar_file:
                logger.debug("Tarring %s files to: %s", len(small_files), tar_file.name)
                self.tar_files(tar_file, small_files)

            # Because we're using the same mechanics to upload the tar file as our regular files,
            # we must jump through the same hoops:
            #   - Generate an md5 for the tar file
            #   - Update the metric store with the filepath/md5 pair (this is used by the UploadWorker
            #     later on)
            tar_md5 = common.generate_md5(tar_file.name, base_64=True, poll_seconds=5)
            self.metric_store.set_dict('file_md5s', tar_file.name, tar_md5)

            # Put the tar file path and md5 pair back into the input queue so that  HttpBatchWorker
            # will pick it up and continue the normal uploading logic chain.
            self.in_queue.put_nowait((tar_file.name, tar_md5))

            # Re-purpose the tar queue (now that its empty and won't be used again. ugh this hideous)
            # and add the tar filepath, and it's md5 to it.
            # After everything has finished uploading, we'll check this queue to retrieve the
            # the tar file and md5 so that we can delete it from local disk and provide the md5
            # as part of the payload for the /finish endpoint.
            self.tar_queue.put_nowait((tar_file.name, tar_md5))

        # Call parent method to resume normal logic
        return super(MD5OutputWorker, self).join()

    @staticmethod
    def tar_files(tar_file, files):
        '''
        Add the given files to the given tar file (file object).  Name the files by using their md5
        value (rather than their actual filepath).
        Note that we can't use the base64 format because the tar format doesn't accept all characters
        (such as a forward slash).  So convert the md5 to a hex format.
        '''
        with tarfile.open(fileobj=tar_file, mode="w") as tar:
            for file_info in files:
                tar.add(file_info["filepath"], arcname=common.convert_base64_to_hex(file_info["md5"]))

    def remove_temp_files(self):
        '''
        Search for any conductor temp .tar files and delete them.
        '''
        pattern = r"conductor-tmp-[\w]+.tar"
        temp_dirpath = tempfile.gettempdir()
        for f in os.listdir(temp_dirpath):
            if re.search(pattern, f, re.I):
                temp_filepath = os.path.join(temp_dirpath, f)
                logger.debug("Cleaning up temp file: %s", temp_filepath)
                try:
                    os.remove(temp_filepath)
                except Exception as e:
                    logger.exception("Failed to delete temporary tar file: %s. Error: %s" % (temp_filepath, e))


class HttpBatchWorker(worker.ThreadWorker):
    '''
    This worker receives a batched dict of (filename: md5) pairs and makes a
    batched http api call which returns a list of (filename: signed_upload_url)
    of files that need to be uploaded.

    Each item in the return list is added to the out_queue.
    '''

    def __init__(self, *args, **kwargs):
        worker.ThreadWorker.__init__(self, *args, **kwargs)
        self.api_client = api_client.ApiClient()
        self.project = kwargs.get('project')

    def make_request(self, job):
        uri_path = '/api/files/get_upload_urls'
        params = {"memcached": True}
        headers = {'Content-Type': 'application/json'}
        data = {"upload_files": job,
                "project": self.project}

        response_str, response_code = self.api_client.make_request(uri_path=uri_path,
                                                                   verb='POST',
                                                                   headers=headers,
                                                                   params=params,
                                                                   data=json.dumps(data),
                                                                   raise_on_error=True,
                                                                   use_api_key=True)

        if response_code == 200:
            url_list = json.loads(response_str)
            return url_list
        if response_code == 204:
            return None
        raise Exception('%s Failed request to: %s\n%s' % (response_code, uri_path, response_str))

    def do_work(self, job, thread_int):
        logger.debug('getting upload urls for %s', job)
        return self.make_request(job)


'''
This worker subscribes to a queue of (path,signed_upload_url) pairs.

For each item on the queue, it determines the size (in bytes) of the files to be
uploaded, and aggregates the total size for all uploads.

It then places the triplet (filepath, upload_url, byte_size) onto the out_queue

The bytes_to_upload arg is used to hold the aggregated size of all files that need
to be uploaded. Note: This is stored as an [int] in order to pass it by
reference, as it needs to be accessed and reset by the caller.
'''


class FileStatWorker(worker.ThreadWorker):

    def __init__(self, *args, **kwargs):
        worker.ThreadWorker.__init__(self, *args, **kwargs)

    def do_work(self, job, thread_int):
        '''
        Job is a dict of filepath: signed_upload_url pairs.
        The FileStatWorker iterates through the dict.
        For each item, it aggregates the filesize in bytes, and passes each
        pair as a tuple to the UploadWorker queue.
        '''

        # iterate through a dict of (filepath: upload_url) pairs
        for path, upload_url in job.iteritems():
            if not os.path.isfile(path):
                return None
            # logger.debug('stat: %s', path)
            byte_count = os.path.getsize(path)

            self.metric_store.increment('bytes_to_upload', byte_count)
            self.metric_store.increment('num_files_to_upload')

            self.put_job((path, upload_url))

        # make sure we return None, so no message is automatically added to the out_queue
        return None


class UploadWorker(worker.ThreadWorker):
    '''
    This worker receives a (filepath: signed_upload_url) pair and performs an upload
    of the specified file to the provided url.
    '''

    def __init__(self, *args, **kwargs):
        worker.ThreadWorker.__init__(self, *args, **kwargs)
        self.chunk_size = 1048576  # 1M
        self.report_size = 10485760  # 10M
        self.api_client = api_client.ApiClient()

    def chunked_reader(self, filename):
        with open(filename, 'rb') as fp:
            while worker.WORKING and not common.SIGINT_EXIT:
                data = fp.read(self.chunk_size)
                if not data:
                    # we are done reading the file
                    break
                # TODO: can we wrap this in a retry?
                yield data

                # report upload progress
                self.metric_store.increment('bytes_uploaded', len(data), filename)

    def do_work(self, job, thread_int):
        filename = job[0]
        upload_url = job[1]
        md5 = self.metric_store.get_dict('file_md5s', filename)
        try:
            return self.do_upload(upload_url, filename, md5)
        except:
            logger.exception("Failed to upload file: %s because of:\n", filename)
            real_md5 = common.get_base64_md5(filename)
            error_message = "ALERT! File %s retried and still failed!\n" % filename
            error_message += "expected md5 is %s, real md5 is %s" % (md5, real_md5)
            logger.error(error_message)
            raise

    @common.DecRetry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def do_upload(self, upload_url, filename, md5):
        '''
        Note that we don't rely on the make_request's own retry mechanism because
        we need to recreate the chunked_reader generator before retrying the request.
        Instead, we wrap this method in a retry decorator.
        '''

        headers = {'Content-MD5': md5,
                   'Content-Type': 'application/octet-stream'}

        return self.api_client.make_request(conductor_url=upload_url,
                                            headers=headers,
                                            data=self.chunked_reader(filename),
                                            verb='PUT',
                                            tries=1,
                                            use_api_key=True)


class Uploader(object):

    sleep_time = 10

    def __init__(self, location=None, thread_count=4, md5_caching=True, database_filepath=None, tar_size_threshold=0):
        '''
        args:
            tar_size_threshold: int/long.  The file size threshold (in bytes) of whether a file is
                tarred into a group with other files vs uploaded independently. A value of 0
                results in disabling all tar functionality.
        '''
        logger.debug("location: %s", location)
        logger.debug("thread_count: %s", thread_count)
        logger.debug("md5_caching: %s", md5_caching)
        logger.debug("database_filepath: %s", database_filepath)
        logger.debug("tar_size_threshold: %s", tar_size_threshold)

        self.thread_count = thread_count
        self.location = location
        self.md5_caching = md5_caching
        self.database_filepath = database_filepath
        self.tar_size_threshold = tar_size_threshold

        self.api_client = api_client.ApiClient()

    def prepare_workers(self):
        logger.debug('preparing workers...')
        common.register_sigint_signal_handler()
        self.num_files_to_process = 0
        self.job_start_time = 0
        self.manager = None

    def create_manager(self, project, md5_only=False):

        if md5_only:
            job_description = [
                (MD5Worker, [], {'thread_count': self.thread_count,
                                 "database_filepath": self.database_filepath,
                                 "md5_caching": self.md5_caching,
                                 "tar_size_threshold": self.tar_size_threshold,
                                 "tar_queue": self.tar_queue}),
                ]
        else:
            job_description = [
                (MD5Worker, [], {'thread_count': self.thread_count,
                                 "database_filepath": self.database_filepath,
                                 "md5_caching": self.md5_caching,
                                 "tar_size_threshold": self.tar_size_threshold,
                                 "tar_queue": self.tar_queue}),


                (MD5OutputWorker, [], {'thread_count': 1,
                                       "tar_queue": self.tar_queue}),
                (HttpBatchWorker, [], {'thread_count': self.thread_count,
                                       "project": project}),
                (FileStatWorker, [], {'thread_count': 1}),
                (UploadWorker, [], {'thread_count': self.thread_count}),
                ]

        manager = worker.JobManager(job_description)
        manager.start()
        return manager

    def report_status(self):
        logger.debug('started report_status thread')
        update_interval = 5
        while self.working:

            # don't report status if we are doing a local_upload
            if not self.upload_id:
                logger.debug('not updating status as we were not provided an upload_id')
                return

            if self.working:
                bytes_to_upload = self.manager.metric_store.get('bytes_to_upload')
                bytes_uploaded = self.manager.metric_store.get('bytes_uploaded')
                try:
                    status_dict = {
                        'upload_id': self.upload_id,
                        'transfer_size': bytes_to_upload,
                        'bytes_transfered': bytes_uploaded,
                        }
                    logger.debug('reporting status as: %s', status_dict)
                    self.api_client.make_request(
                        '/uploads/%s/update' % self.upload_id,
                        data=json.dumps(status_dict),
                        verb='POST', use_api_key=True)

                except Exception:
                    logger.error('could not report status:')
                    logger.error(traceback.print_exc())
                    logger.error(traceback.format_exc())

            time.sleep(update_interval)

    def create_report_status_thread(self):
        logger.debug('creating reporter thread')
        thd = Thread(name="ReporterThread", target=self.report_status)
        thd.daemon = True
        thd.start()

    @staticmethod
    def estimated_time_remaining(elapsed_time, percent_complete):
        '''
        This method estimates the time that is remaining, given the elapsed time
        and percent complete.

        It uses the following formula:

        let;
          t0 = elapsed time
          P = percent complete (0 <= n <= 1)

        time_remaining = (t0 - t0 * P) / P

        which is derived from percent_complete = elapsed_time / (elapsed_time + time_remaining)
        '''
        if not percent_complete:
            return -1

        estimated_time = (elapsed_time - elapsed_time * percent_complete) / percent_complete
        return estimated_time

    @staticmethod
    def convert_byte_count_to_string(byte_count, transfer_rate=False):
        '''
        Converts a byte count to a string denoting its size in GB/MB/KB
        '''
        if byte_count > 2 ** 30:
            return str(round(byte_count / float(2 ** 30), 1)) + ' GB'
        elif byte_count > 2 ** 20:
            return str(round(byte_count / float(2 ** 20), 1)) + ' MB'
        elif byte_count > 2 ** 10:
            return str(round(byte_count / float(2 ** 10), 1)) + ' KB'
        else:
            return str(byte_count) + ' B'

    @staticmethod
    def convert_time_to_string(time_remaining):
        if time_remaining > 3600:
            return str(round(time_remaining / float(3600), 1)) + ' hours'
        elif time_remaining > 60:
            return str(round(time_remaining / float(60), 1)) + ' minutes'
        else:
            return str(round(time_remaining, 1)) + ' seconds'

    def upload_status_text(self):
        num_files_to_upload = self.manager.metric_store.get('num_files_to_upload')
        files_to_upload = str(num_files_to_upload)
        files_to_analyze = str(self.num_files_to_process)

        if self.job_start_time:
            elapsed_time = int(time.time()) - self.job_start_time
        else:
            elapsed_time = 0

        bytes_to_upload = self.manager.metric_store.get('bytes_to_upload')
        bytes_uploaded = self.manager.metric_store.get('bytes_uploaded')
        if bytes_to_upload:
            percent_complete = bytes_uploaded / float(bytes_to_upload)
        else:
            percent_complete = 0

        if elapsed_time:
            transfer_rate = bytes_uploaded / elapsed_time
        else:
            transfer_rate = 0

        unformatted_text = '''
################################################################################
     files to process: {files_to_analyze}
      files to upload: {files_to_upload}
       data to upload: {bytes_to_upload}
             uploaded: {bytes_uploaded}
         elapsed time: {elapsed_time}
     percent complete: {percent_complete}
        transfer rate: {transfer_rate}
       time remaining: {time_remaining}
        file progress:
'''

        bytes_to_upload = self.manager.metric_store.get('bytes_to_upload')
        bytes_uploaded = self.manager.metric_store.get('bytes_uploaded')

        formatted_text = unformatted_text.format(
            files_to_analyze=files_to_analyze,
            files_to_upload=files_to_upload,
            bytes_to_upload=self.convert_byte_count_to_string(bytes_to_upload),
            bytes_uploaded=self.convert_byte_count_to_string(bytes_uploaded),
            elapsed_time=self.convert_time_to_string(elapsed_time),
            percent_complete=str(round(percent_complete * 100, 1)) + ' %',
            transfer_rate=self.convert_byte_count_to_string(transfer_rate) + '/s',
            time_remaining=self.convert_time_to_string(
                self.estimated_time_remaining(elapsed_time, percent_complete)),
            )

        file_progress = self.manager.metric_store.get_dict('files')
        for filename in file_progress:
            formatted_text += "%s: %s\n" % (filename, file_progress[filename])

        formatted_text += "################################################################################"

        return formatted_text

    def print_status(self):
        logger.debug('starting print_status thread')
        update_interval = 3

        while self.working:
            try:
                logger.info(self.manager.worker_queue_status_text())
                logger.info(self.upload_status_text())
            except Exception:
                logger.exception("#### Print Status Thread exception ####\n")
            self.sleep(update_interval)

    def create_print_status_thread(self):
        logger.debug('creating console status thread')
        thd = Thread(name="PrintStatusThread", target=self.print_status)

        # make sure threads don't stop the program from exiting
        thd.daemon = True

        # start thread
        thd.start()

    def mark_upload_finished(self, upload_id, upload_files, tar_md5=None):

        data = {'upload_id': upload_id,
                'status': 'server_pending',
                'upload_files': upload_files,
                'upload_bundle_md5': tar_md5}

        self.api_client.make_request('/uploads/%s/finish' % upload_id,
                                     data=json.dumps(data),
                                     compress=True,
                                     verb='POST',
                                     use_api_key=True)
        return True

    def mark_upload_failed(self, error_message, upload_id):
        logger.error('failing upload due to: \n%s' % error_message)

        # report error_message to the app
        self.api_client.make_request('/uploads/%s/fail' % upload_id,
                                     data=error_message,
                                     verb='POST', use_api_key=True)

        return True

    def handle_upload_response(self, project, upload_files, upload_id=None, md5_only=False):
        '''
        This is a reallly confusing method and should probably be split into
        to clear logic branches: one that is called when in daemon mode, and
        one that is not.
        If not called in daemon mode (local_upload=True), then md5_only is True
        and project is not None.Otherwise we're in daemon mode, where the project
        information is not required because the daemon will only be fed uploads
        by the app which have valid projects attached to them.
        '''
        try:

            logger.info("%s", "  NEXT UPLOAD  ".center(30, "#"))
            logger.info('project: %s', project)
            logger.info('upload_id is %s', upload_id)
            logger.info('upload_files %s:(truncated)\n\t%s',
                        len(upload_files), "\n\t".join(upload_files.keys()[:5]))

            # reset counters
            self.num_files_to_process = len(upload_files)
            self.job_start_time = int(time.time())
            self.upload_id = upload_id
            self.job_failed = False

            # signal the reporter to start working
            self.working = True

            self.prepare_workers()

            # create a queue for files that will be tarred into one file
            self.tar_queue = Queue.Queue()

            # create worker pools
            self.manager = self.create_manager(project, md5_only)

            # create reporters
            logger.debug('creating report status thread...')
            self.create_report_status_thread()
            logger.info('creating console status thread...')
            self.create_print_status_thread()

            # load tasks into worker pools
            for path, md5 in upload_files.iteritems():
                self.manager.add_task((path, md5))

            # wait for work to finish
            error_message = self.manager.join()
            logger.debug("error_message: %s", error_message)

            # signal to the reporter to stop working
            self.working = False
            logger.info('done uploading files')

            if error_message:
                return "\n".join(error_message)

            # Check if there is a tar file in this queue. There should none or one.
            tar_items = worker.empty_queue(self.tar_queue)
            assert len(tar_items) <= 1, "Got more than one tar file: %s" % tar_items
            tar_filepath, tar_md5 = tar_items[0] if tar_items else (None, None)

            #  Despite storing lots of data about new uploads, we will only send back the things
            #  that have changed, to keep payloads small.
            if self.upload_id:
                upload_files = self.return_md5s()
                # Remove the tar file from the upload files (since this isn't a customer's actual file,
                # simply our own temporary transport file)
                upload_files.pop(tar_filepath, None)
                self.mark_upload_finished(self.upload_id, upload_files, tar_md5=tar_md5)

            if tar_filepath:
                logger.debug("Removing temporary tar file: %s", tar_filepath)
                try:
                    os.remove(tar_filepath)
                except Exception as e:
                    logger.exception("Failed to delete temporary tar file: %s. Error: %s" % tar_filepath, e)

        except Exception:
            logger.exception("######## ENCOUNTERED EXCEPTION #########\n")
            return traceback.format_exc()

    @classmethod
    def sleep(cls, seconds):
        for _ in xrange(seconds):
            if common.SIGINT_EXIT:
                return
            time.sleep(1)

    def main(self, run_one_loop=False):
        logger.info('Uploader Started. Checking for uploads...')

        while not common.SIGINT_EXIT:
            try:
                # TODO: we should pass args as url params, not http data
                data = {}
                data['location'] = self.location
                logger.debug("Data: %s", data)
                resp_str, resp_code = self.api_client.make_request('/uploads/client/next',
                                                                   data=json.dumps(data),
                                                                   verb='PUT', use_api_key=True)
                if resp_code == 204:
                    logger.debug('no files to upload')
                    sys.stdout.write('.')
                    sys.stdout.flush()
                    self.sleep(self.sleep_time)
                    continue
                elif resp_code != 201:
                    logger.error('received invalid response code from app %s', resp_code)
                    logger.error('response is %s', resp_str)
                    self.sleep(self.sleep_time)
                    continue

                print ''  # to make a newline after the 204 loop
                # logger.debug('recieved next upload from app: %s\n\t%s', resp_code, resp_str)

                try:
                    json_data = json.loads(resp_str)
                    upload = json_data.get("data", {})
                except ValueError:
                    logger.error('response was not valid json: %s', resp_str)
                    self.sleep(self.sleep_time)
                    continue

                upload_files = upload['upload_files']
                upload_id = upload['id']
                project = upload['project']

                error_message = self.handle_upload_response(project, upload_files, upload_id)
                if error_message:
                    self.mark_upload_failed(error_message, upload_id)

            except KeyboardInterrupt:
                logger.info("ctrl-c exit")
                break
            except:
                logger.exception('Caught exception:\n')
                self.sleep(self.sleep_time)
                continue

        logger.info('exiting uploader')

    def return_md5s(self):
        '''
        Return a dictionary of the filepaths and their md5s that were generated
        upon uploading
        '''
        return self.manager.metric_store.get_dict('file_md5s')


def set_logging(level=None, log_dirpath=None):
    log_filepath = None
    if log_dirpath:
        log_filepath = os.path.join(log_dirpath, "conductor_ul_log")
    loggeria.setup_conductor_logging(logger_level=level,
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
    logger.debug("Parsed args: %s", args_dict)

    # Set up logging
    log_level_name = args_dict.pop("log_level", None) or CONFIG.get("log_level")
    log_level = loggeria.LEVEL_MAP.get(log_level_name)
    log_dirpath = args_dict.pop("log_dir", None) or CONFIG.get("log_dir")
    set_logging(log_level, log_dirpath)

    location = resolve_arg("location", args_dict, CONFIG)
    thread_count = resolve_arg("thread_count", args_dict, CONFIG)
    md5_caching = resolve_arg("md5_caching", args_dict, CONFIG)
    database_filepath = resolve_arg("database_filepath", args_dict, CONFIG) or client_db.get_default_db_filepath()
    tar_size_threshold = resolve_arg("tar_size_threshold", args_dict, CONFIG)
    uploader = Uploader(
        location=location,
        thread_count=thread_count,
        md5_caching=md5_caching,
        database_filepath=database_filepath,
        tar_size_threshold=tar_size_threshold,
        )
    uploader.main()


def get_file_info(filepath):
    '''
    For the given filepath return the following information in a dictionary:
        "filepath": filepath (str)
        "modtime": modification time (datetime.datetime)
        "size": filesize in bytes (int)

    '''
    assert os.path.isfile(filepath), "Filepath does not exist: %s" % filepath
    stat = os.stat(filepath)
    modtime = datetime.datetime.fromtimestamp(stat.st_mtime)

    return {"filepath": filepath,
            "modtime": modtime,
            "size": stat.st_size}


def resolve_args(args):
    '''
    Resolve all arguments, reconsiling differences between command line args
    and config.yml args.  See resolve_arg function.
    '''
    args["md5_caching"] = resolve_arg("md5_caching", args, CONFIG)
    args["database_filepath"] = resolve_arg("database_filepath", args, CONFIG)
    args["location"] = resolve_arg("location", args, CONFIG)
    args["thread_count"] = resolve_arg("thread_count", args, CONFIG)
    return args


def resolve_arg(arg_name, args, config, default=None):
    '''
    Helper function to resolve the value of an argument.
    The order of resolution is:
    1. Check whether the user explicitly specified the argument when calling/
       instantiating the class. If so, then use it, otherwise...
    2. Attempt to read it from the config.yml. Note that the config also queries
       environment variables to populate itself with values.
       If the value is in the config then use it, otherwise...
    3. return None

    '''
    # Attempt to read the value from the args
    value = args.get(arg_name)
    # If the arg is not None, it indicates that the arg was explicity
    # specified by the caller/user, and it's value should be used
    if value != None:
        return value
    # Otherwise use the value in the config if it's there, otherwise default to None
    return config.get(arg_name, default)


# @common.dec_timer_exitlog_level=logging.DEBUG
# def test_md5_system(dirpath):
#     '''
#     Recurse the given directory, md5-checking all files and returning a dictionary
#     whose key is a filepath and whose value is the md5 value for that file.
#     When run successively, only md5 checkin when the file has changed.
#     Keep track of "changed files" by using a sqlite db to "cache" every file
#     that's been md5 checked (including it's modtime and filesize) to intellegently
#     determine (assume) whether a file has actually changed or not.
#
#     Each file entry (row) in the database is uniquely identified by the filepath,
#     (using the filepath as the Primary Key).
#     '''
#     BYTES_1MB = 1024.0 ** 2
#     BYTES_1GB = 1024.0 ** 3
#
#
#     # Get all files found within the given directory
#     logger.debug("Reading files from: %s", dirpath)
#     filepaths = [filepath for filepath in file_utils.get_files(dirpath, recurse=True) if os.path.exists(filepath)]
#
#
#     # Get the caches for all files
#     logger.debug("Getting files info from disk")
#     files_info = dict([(filepath, get_file_info(filepath)) for filepath in filepaths])
#
#     logger.debug("Getting files cache from db")
#     cached_files = get_cached_files(files_info)
#     logger.debug("cached_files: %s", len(cached_files))
#
#     cached_files_size = sum([file_info["size"] for file_info in cached_files.values()])
#     logger.debug("cached_files_size: %s GB", cached_files_size / BYTES_1GB)
#
#     # Figure out which files didn't have valid caches in the db
#     uncached_filepaths = [filepath for filepath in filepaths if filepath not in cached_files]
#     logger.debug("uncached files: %s", len(uncached_filepaths))
#
#     logger.debug("Generating md5s..")
#     new_md5s = {}
#     # For any files that aren't cached, get the md5 data:
#     for uncached_filepath in uncached_filepaths:
#         logger.debug("Getting md5: %s", uncached_filepath)
#         md5 = common.get_base64_md5(filepath)
#         new_md5s[uncached_filepath] = md5
#
#
#     # Update the database cache with the new md5 info
#     new_files_info = {}
#     for file_path, md5 in new_md5s.iteritems():
#         file_info = files_info[file_path]
#         file_info["md5"] = md5
#         new_files_info[file_path] = file_info
#
#     unchached_files_size = sum([file_info["size"] for file_info in new_files_info.values()])
#     logger.debug("unchached_files_size: %s GB", unchached_files_size / BYTES_1GB)
#
#
#     if new_files_info:
#         logger.debug("adding %s new files to db", len(new_files_info))
#         client_db.add_files(new_files_info.values())
#
#     # Return a dicationary of final md5s
#     md5s = {}
#     for file_info in cached_files.values():
#         filepath = file_info["filepath"]
#         md5s[filepath] = file_info.get("md5") or new_files_info[filepath]["md5"]
#
#     logger.debug("Complete")
#     return md5s
