import datetime
import hashlib
import time
import json
import logging
import os
import Queue
import sys
import thread
from threading import Thread
import traceback

from conductor import CONFIG
from conductor.lib import api_client, common, worker, client_db, loggeria

LOG_FORMATTER = logging.Formatter('%(asctime)s  %(name)s%(levelname)9s  %(threadName)s:  %(message)s')

# Files larger than 5GB will be uploaded in parts of this size
# This value must be in sync with the File API
# TODO: Query File API for this value
MULTIPART_SIZE = 1 * 1024 * 1024 * 1024

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
        super(MD5Worker, self).__init__(*args, **kwargs)

    def do_work(self, job, thread_int):
        logger.debug('job is %s', job)
        filename, submission_time_md5 = job
        assert isinstance(filename, (str, unicode)), "Filepath not of expected type. Got %s" % type(filename)
        filename = str(filename)
        current_md5 = self.get_md5(filename)
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
        size_bytes = os.path.getsize(filename)
        return (filename, current_md5, size_bytes)

    def get_md5(self, filepath):
        '''
        For the given filepath, return it's md5.

        Use the sqlite db cache to retrive this (if the cache is valid),
        otherwise generate the md5 from scratch
        '''
        # If md5 caching is disable, then just generate the md5 from scratch
        if not self.md5_caching:
            return common.generate_md5(filepath, base_64=True, poll_seconds=5)

        # Otherwise attempt to use the md5 cache
        file_info = get_file_info(filepath)
        file_cache = client_db.FilesDB.get_cached_file(file_info,
                                                       db_filepath=self.database_filepath,
                                                       thread_safe=True)
        if not file_cache:
            logger.debug("No md5 cache available for file: %s", filepath)
            md5 = common.generate_md5(filepath, base_64=True, poll_seconds=5)
            file_info["md5"] = md5
            self.cache_file_info(file_info)
            return md5

        logger.debug("Using md5 cache for file: %s", filepath)
        return file_cache["md5"]

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

    def __init__(self, *args, **kwargs):
        super(MD5OutputWorker, self).__init__(*args, **kwargs)
        self.batch_size = 20  # the controlls the batch size for http get_signed_urls
        self.wait_time = 1
        self.batch = []

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
            self.batch = []

    def target(self, thread_int):

        while not common.SIGINT_EXIT:
            try:
                # block on the queue with a self.wait_time second timeout
                file_md5_tuple = self.in_queue.get(True, self.wait_time)

                self.check_for_poison_pill(file_md5_tuple)

                # add file info to the batch list
                self.batch.append({
                    'path': file_md5_tuple[0],
                    'hash': file_md5_tuple[1],
                    'size_bytes': file_md5_tuple[2],
                })

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


class HttpBatchWorker(worker.ThreadWorker):
    '''
    This worker receives a batched list of file info and makes a
    batched http api call which returns a list of files with upload
    info that need to be uploaded.

    in_queue: {
        "path": file_path,
        "hash": md5,
        "size_bytes": 123
    }

    out_queue: [
        {
            "hash": md5,
            "url": signed_upload_url,
            "multipart": True,
            "path": file_path,
            "upload_id": upload_id,
            "parts": [
                signed_multipart_url,
            ]
        }
    ]

    Each item in the return list is added to the out_queue.
    '''

    def __init__(self, *args, **kwargs):
        super(HttpBatchWorker, self).__init__(*args, **kwargs)
        self.api_client = api_client.ApiClient()
        self.project = kwargs.get('project')

    def make_request(self, job):
        uri_path = '/api/files/v2/get_upload_urls'
        headers = {'Content-Type': 'application/json'}
        data = {"upload_files": job,
                "project": self.project}

        response_str, response_code = self.api_client.make_request(uri_path=uri_path,
                                                                   verb='POST',
                                                                   headers=headers,
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
This worker subscribes to a queue of file upload info.

For each item on the queue, it determines the size (in bytes) of the files to be
uploaded, and aggregates the total size for all uploads.

It then passes the input file upload info back into the out_queue

The bytes_to_upload arg is used to hold the aggregated size of all files that need
to be uploaded. Note: This is stored as an [int] in order to pass it by
reference, as it needs to be accessed and reset by the caller.
'''


class FileStatWorker(worker.ThreadWorker):
    def __init__(self, *args, **kwargs):
        super(FileStatWorker, self).__init__(*args, **kwargs)

    def do_work(self, job, thread_int):
        '''
        Job is a list of file upload info returned from File API.
        The FileStatWorker iterates through the list.
        For each item, it aggregates the filesize in bytes, and passes
        the upload info into the UploadWorker queue.
        '''

        # iterate through a list of file upload info dicts
        for upload in job:
            path = upload["path"]
            if not os.path.isfile(path):
                return None
            # logger.debug('stat: %s', path)
            byte_count = os.path.getsize(path)

            self.metric_store.increment('bytes_to_upload', byte_count)
            self.metric_store.increment('num_files_to_upload')

            self.put_job(upload)

        # make sure we return None, so no message is automatically added to the out_queue
        return None


class UploadWorker(worker.ThreadWorker):
    '''
    This worker receives file upload info and performs an upload
    of the specified file to the provided url.
    '''

    def __init__(self, *args, **kwargs):
        super(UploadWorker, self).__init__(*args, **kwargs)
        self.chunk_size = 1048576  # 1M
        self.report_size = 10485760  # 10M
        self.api_client = api_client.ApiClient()
        self.project = kwargs.get('project')

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
        '''
        If the file is larger than 5GB on S3, File API will return
        multiple urls for a multipart upload.
        '''
        filename = job["path"]
        md5 = self.metric_store.get_dict('file_md5s', filename)
        try:
            if job["multipart"]:
                return self.do_multipart_upload(job, filename, md5)
            return [self.do_upload(job["url"], filename, md5)]
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
        Note that for GCS we don't rely on the make_request's own retry mechanism because
        we need to recreate the chunked_reader generator before retrying the request.
        Instead, we wrap this method in a retry decorator.

        We cannot reuse make_request method for S3 because it adds auth headers that
        S3 does not accept. S3 also requires additional signatures to support chunked data.
        '''

        if "amazonaws" in upload_url:
            headers = {'Content-Type': 'application/octet-stream'}

            with open(filename, 'rb') as fh:
                # TODO: update make_request to be flexible with auth headers
                # TODO: support chunked or streamed data
                return self.api_client._make_request(verb="PUT",
                                                     conductor_url=upload_url,
                                                     headers=headers,
                                                     params=None,
                                                     data=fh)

        else:
            headers = {'Content-MD5': md5,
                       'Content-Type': 'application/octet-stream'}

            return self.api_client.make_request(conductor_url=upload_url,
                                                headers=headers,
                                                data=self.chunked_reader(filename),
                                                verb='PUT',
                                                tries=1,
                                                use_api_key=True)

    @common.DecRetry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def do_multipart_upload(self, job, filename, md5):
        '''
        Files larger than 5GB will be split into 1GB parts and hydrated in S3
        once all parts are uploaded.

        On successful part upload to S3, it will return an ETag. This value must be
        tracked along with the part number in order to complete and hydrate the file in S3.

        The multipart completion call can take a long time on larger files. Tests on
        larger files (~100GB) took between 1 and 2 seconds to complete.
        '''
        uploads = []
        complete_payload = {
            "upload_id": job["upload_id"],
            "hash": md5,
            "completed_parts": [],
            "project": self.project
        }

        # iterate over parts and upload
        for part_number, part_url in enumerate(job["parts"]):
            resp = self.do_part_upload(part_url, filename, part_number=part_number)
            uploads.append(resp)
            completed_part = {
                "PartNumber": part_number,
                "ETag": resp.headers['ETag'].strip('"')
            }
            complete_payload["completed_parts"].append(completed_part)

        # Complete multipart upload in order to hydrate file in S3 for availability
        uri_path = '/api/files/v2/complete_multipart'
        headers = {'Content-Type': 'application/json'}
        self.api_client.make_request(uri_path=uri_path,
                                     verb='POST',
                                     headers=headers,
                                     data=json.dumps(complete_payload),
                                     raise_on_error=True,
                                     use_api_key=True)

        return uploads

    def do_part_upload(self, upload_url, filename, part_number):
        with open(filename, 'rb') as fh:
            # seek to the correct part position
            start = (part_number - 1) * MULTIPART_SIZE
            fh.seek(start)

            # read up to MULTIPART_SIZE
            data = fh.read(MULTIPART_SIZE)

            # calculate md5 in order to compare with returned ETag later
            file_hash = hashlib.md5()
            file_hash.update(data)
            digest = file_hash.hexdigest()

            # upload part
            resp = self.api_client._make_request(verb="PUT",
                                                 conductor_url=upload_url,
                                                 headers={},
                                                 params=None,
                                                 data=data)

            # verify data
            etag = resp.headers['ETag']
            if etag.strip('"') != digest:
                error_message = "ETag for multipart upload part does not match expected md5\n"
                error_message += "expected md5 is %s, returned md5 is %s" % (digest, etag)
                raise Exception(error_message)
            return resp


class Uploader(object):
    sleep_time = 10

    def __init__(self, args=None):
        logger.debug("Uploader.__init__")
        self.api_client = api_client.ApiClient()
        self.args = args or {}
        logger.debug("args: %s", self.args)

        self.location = self.args.get("location")
        self.project = self.args.get("project")

    def prepare_workers(self):
        logger.debug('preparing workers...')
        common.register_sigint_signal_handler()
        self.num_files_to_process = 0
        self.job_start_time = 0
        self.manager = None

    def create_manager(self, project, md5_only=False):
        if md5_only:
            job_description = [
                (MD5Worker, [], {'thread_count': self.args['thread_count'],
                                 "database_filepath": self.args['database_filepath'],
                                 "md5_caching": self.args['md5_caching']})
            ]
        else:
            job_description = [
                (MD5Worker, [], {'thread_count': self.args['thread_count'],
                                 "database_filepath": self.args['database_filepath'],
                                 "md5_caching": self.args['md5_caching']}),

                (MD5OutputWorker, [], {'thread_count': 1}),
                (HttpBatchWorker, [], {'thread_count': self.args['thread_count'],
                                       "project": project}),
                (FileStatWorker, [], {'thread_count': 1}),
                (UploadWorker, [], {'thread_count': self.args['thread_count'], "project": project}),
            ]

        manager = worker.JobManager(job_description)
        manager.start()
        return manager

    def report_status(self):
        logger.debug('started report_status thread')
        update_interval = 5
        while True:

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

        def sleep():
            time.sleep(update_interval)

        while True:
            if self.working:
                try:
                    logger.info(self.manager.worker_queue_status_text())
                    logger.info(self.upload_status_text())
                except Exception, e:
                    print e
                    print traceback.format_exc()
                    # pass
            sleep()

    def create_print_status_thread(self):
        logger.debug('creating console status thread')
        thd = Thread(name="PrintStatusThread", target=self.print_status)

        # make sure threads don't stop the program from exiting
        thd.daemon = True

        # start thread
        thd.start()

    def mark_upload_finished(self, upload_id, upload_files):

        data = {'upload_id': upload_id,
                'status': 'server_pending',
                'upload_files': upload_files}

        self.api_client.make_request('/uploads/%s/finish' % upload_id,
                                     data=json.dumps(data),
                                     verb='POST', use_api_key=True)
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

            #  Despite storing lots of data about new uploads, we will only send back the things
            #  that have changed, to keep payloads small.
            if self.upload_id:
                finished_upload_files = {path: {"source": path,
                                                "md5": md5}
                                         for path, md5 in self.return_md5s().iteritems()}

                self.mark_upload_finished(self.upload_id, finished_upload_files)

        except:
            return traceback.format_exc()

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
                    time.sleep(self.sleep_time)
                    continue
                elif resp_code != 201:
                    logger.error('received invalid response code from app %s', resp_code)
                    logger.error('response is %s', resp_str)
                    time.sleep(self.sleep_time)
                    continue

                print ''  # to make a newline after the 204 loop
                # logger.debug('recieved next upload from app: %s\n\t%s', resp_code, resp_str)

                try:
                    json_data = json.loads(resp_str)
                    upload = json_data.get("data", {})
                except ValueError:
                    logger.error('response was not valid json: %s', resp_str)
                    time.sleep(self.sleep_time)
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
                time.sleep(self.sleep_time)
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

    # Set up logging
    log_level_name = args_dict.get("log_level") or CONFIG.get("log_level")
    log_level = loggeria.LEVEL_MAP.get(log_level_name)
    log_dirpath = args_dict.get("log_dir") or CONFIG.get("log_dir")
    set_logging(log_level, log_dirpath)
    logger.debug('Uploader parsed_args is %s', args_dict)
    resolved_args = resolve_args(args_dict)
    uploader = Uploader(resolved_args)
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
    args['thread_count'] = resolve_arg('thread_count', args, CONFIG)

    return args


def resolve_arg(arg_name, args, config):
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
    return config.get(arg_name)

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
