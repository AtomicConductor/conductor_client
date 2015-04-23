#!/usr/bin/env python

""" Command Line General Submitter for sending jobs and uploads to Conductor

"""


import os
import sys
import re
import glob
import time
import argparse
import httplib2
import urllib2
import json
import random
import datetime
import tempfile
import getpass
import subprocess
import multiprocessing

from apiclient import discovery
from apiclient.http import MediaFileUpload
from apiclient.errors import HttpError
from oauth2client import file as oauthfile
from oauth2client import client
from oauth2client import tools

import submit_settings

_this_dir = os.path.dirname(os.path.realpath(__file__))

class Submit():
    """ Conductor Submission 
    Command Line Usage:
        $ python conductor_submit.py -upload_file /path/to/upload_file.txt -frames 1001-1100 -cmd 

    Help: 
        $ python conductor_submit.py -h
    """
    def __init__(self, args):
        self.timeid = int(time.time())
        self.consume_args(args)

    @classmethod
    def from_commmand_line(cls):
        args = cls._parseArgs()
        return cls(args)

    def consume_args(self, args):
        self.raw_command = args['cmd']
        self.user = args['user']
        self.frames = args['frames']
        self.resource = args['resource']
        self.priority = args['priority']
        self.upload_dep = args['upload_dependent']
        self.output_path = args['output_path']
        self.upload_file = args['upload_file']
        self.upload_paths = args['upload_paths']
        self.upload_only = args['upload_only']
        self.postcmd = args['postcmd']
        self.skip_time_check = args['skip_time_check']
        self.force = args['force']

        # TODO: switch this behavior to use file size plus md5 instead
        # For now always default nuke uploads to skip time check
        if self.upload_only or "nuke-render" in self.raw_command:
            self.skip_time_check = True

        if self.upload_paths is None:
            self.upload_paths = []


    def _parseArgs(self):
        parser = argparse.ArgumentParser(description=self.__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument("--cmd",
            help="execute this command.",
            type=str)
        parser.add_argument("--frames",
            help="frame range to execute over.",
            type=str)
        parser.add_argument("--user",
            help="Username to submit as",
            type=str,
            default=getpass.getuser(),
            required=False)
        parser.add_argument("--output_path",
            help="path to copy renders to",
            type=str,
            required=False)
        parser.add_argument("--upload_file",
            help="The path to an upload file",
            type=str,
            required=False)
        parser.add_argument("--upload_paths",
            help="Paths to upload",
            nargs="*")
        parser.add_argument("--resource",
            help="resource pool to submit jobs to, defaults to show name.",
            type=str,
            required=False)
        parser.add_argument("--priority",
            help="Set the priority of the submitted job. Default is 5",
            type=str,
            required=False)
        parser.add_argument("--upload_dependent",
            help="job id of another job that this should be upload dependent on.",
            type=str,
            required=False)
        parser.add_argument("--upload_only",
            help="Only upload the files, don't start the render",
            action='store_true')
        parser.add_argument("--force",
            help="Do not check for existing uploads, force a new upload",
            action='store_true')
        parser.add_argument("--postcmd",
            help="Run this command once the entire job is complete and downloaded",
            type=str,
            required=False)
        parser.add_argument("--skip_time_check",
            action='store_true',
            default=False,
            help="Don't perform a time check between local and cloud")

        return parser.parse_args()




    def get_upload_files(self):
        """ When given an upload file, return a list of files.
            Expects a file containing string absolute file paths,
            seperated by commas.
        """
        files = []
        if self.upload_file:
            with open(self.upload_file, 'r') as f:
                contents = f.read()
            files = contents.split(',')
        return list(set(self.upload_paths + [f.strip() for f in files]))


    def get_token(self):
        token_path = os.path.join(os.path.dirname(__file__), 'auth/CONDUCTOR_TOKEN.pem')
        if not os.path.exists(token_path):
            raise IOError("Could not locate .pem file: %s" % token_path)
        with open(token_path, 'r') as f:
            user = f.read()
        userpass = "%s:unused" % user.rstrip()
        return userpass

    def send_job(self, cloud_upload_file=None):
        userpass = self.get_token()
        if self.raw_command and self.frames:
            url = "jobs/"
            if not self.resource:
                try:
                    self.resource = os.environ['AF_PROJECT_NAME']
                except KeyError, e:
                    print "No project detected, using 'af' instead"
                    self.resource = "af"

            submit_dict = {'owner':self.user,
                           'resource':self.resource.lower(),
                           'frame_range':self.frames,
                           'command':self.raw_command,
                           'instance_type':'n1-standard-16'}
            if cloud_upload_file:
                submit_dict['upload_file'] = cloud_upload_file
            if self.priority:
                submit_dict['priority'] = self.priority
            if self.upload_dep:
                submit_dict['dependent'] = self.upload_dep
            if self.postcmd:
                submit_dict['postcmd'] = self.postcmd
            if self.output_path:
                submit_dict['output_path'] = self.output_path
        elif self.upload_only and cloud_upload_file:
            url = "jobs/"
            submit_dict = {'upload_file': cloud_upload_file,
                           'owner': self.user,
                           'frame_range':"x",
                           'command':'upload only',
                           'instance_type':'n1-standard-1'}
        else:
            raise BadArgumentError('The supplied arguments could not submit a valid request.')

        json_dict = json.dumps(submit_dict)
        conductor_url = "https://3.atomic-light-001.appspot.com/%s" % url
        password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(None, conductor_url, userpass.split(':')[0], 'unused')
        auth = urllib2.HTTPBasicAuthHandler(password_manager)
        opener = urllib2.build_opener(auth)
        urllib2.install_opener(opener)


        req = urllib2.Request(conductor_url,
                            headers={'Content-Type':'application/json'},
                            data=json_dict)
        handler = urllib2.urlopen(req)
        f = handler.read()
        return f

    def main(self):
        upload_file = None
        # Handle uploads
        if self.upload_file or self.upload_paths:
            upload_files = self.get_upload_files()
            uploads = Uploads(upload_files, self.timeid, self.skip_time_check, force=self.force)
            upload_file = uploads.run_uploads()
            if upload_file:
                print upload_file
            else:
                print "Upload Not Needed."
                if self.upload_only:
                    return
        # Submit the job to conductor
        if upload_file:
            resp = self.send_job(upload_file)
        else:
            resp = self.send_job()
        print resp


class Uploads():
    """ Manages Uploads from Local File System to Conductor """
    def __init__(self, upload_files, timeid, skip_time_check=False, force=False):
        self._secret_key = "%s/google/atomic-light-001.p12" % _this_dir
        self._gcloud_cmd = "gcloud auth activate-service-account %s --key-file %s --project %s" % (
                                submit_settings._SERVICE_ACCOUNT_EMAIL, self._secret_key, submit_settings._CLOUD_PROJECT)
        self._storage_cmd = "gsutil"
        self.timeid = timeid
        self.service = self._auth_service()
        self.set_service_account()
        self.upload_files = upload_files
        self.skip_time_check = skip_time_check
        self.force = force

    def _auth_service(self):
        credentials = self._get_credentials()
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = discovery.build('storage', submit_settings._API_VERSION, http=http)
        return service

    def _get_credentials(self):
        flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
        storage = oauthfile.Storage(os.path.join(os.path.dirname(__file__), 'auth', 'conductor.dat'))
        credentials = storage.get()
        if credentials is None or credentials.invalid:
            credentials = tools.run_flow(submit_settings.FLOW, storage, flags)
        return credentials

    def set_service_account(self):
        results, out, err = self.call_cmd(self._gcloud_cmd)
        if results.returncode != 0:
            raise IOError("Could not authenticate using the service account! - %s \n %s" % (out, err))

    def handle_stalled(error, iters):
      if iters > submit_settings.NUM_RETRIES:
        print('Failed to make progress for too many consecutive iterations.')
        raise error

      sleeptime = random.random() * (2 ** iters)
      print ('Caught exception (%s). Sleeping for %s seconds before retry #%d.'
             % (str(error), sleeptime, iters))
      time.sleep(sleeptime)

    def chunk_request(self, req):
        stalled_iters = 0
        resp = None
        while resp  is None:
            error = None
            try:
                progress, resp = req.next_chunk()
                if progress:
                    sys.stdout.write("\rUpload %d%%" % (100 * progress.progress()))
                    sys.stdout.flush()
            except HttpError, e:
                if e.resp.status < 500:
                    raise
            except submit_settings.RETRYABLE_ERRORS, e:
                error = e

            if error:
                stalled_iter += 1
                handle_stalled(error, stalled_iter)
            else:
                stalled_iter = 0
        return json.dumps(resp, indent=4)

    def run_request(self, req):
        resp = None
        tries = 0
        while resp is None:
            error = None
            try:
                resp = req.execute()
            except HttpError, e:
                if e.resp.status == 401:
                    self.service = self._auth_service()
                    self.set_service_account()
                    error = e
                elif e.resp.status < 500:
                    raise
            except submit_settings.RETRYABLE_ERRORS, e:
                error = e
            if error:
                tries += 1
                if tries > submit_settings.NUM_RETRIES:
                    print "Reached maximum number of retries"
                    raise error
                else:
                    sleeptime = random.random() * (2 ** tries)
                    time.sleep(sleeptime)
            else:
                tries = 0
        return resp

    def is_upload_needed(self, filename, unix_file):
        """ 
        Determine if an upload is needed.
        """
        fields_to_return = "items(name, size, updated)"
        gs_file = "%s%s" % (submit_settings._UPLOAD_POINT, unix_file)
        req = self.service.objects().list(bucket=submit_settings._BUCKET_NAME,
                    prefix=gs_file, fields=fields_to_return)

        resp = self.run_request(req)

        if resp == {}:
            print "UPP resp"
            return True

        cloud_size = resp['items'][0]['size']
        local_size = os.path.getsize(filename)

        if not self.skip_time_check:
            cloud_time_str = resp['items'][0]['updated']

            cloud_time = datetime.datetime.strptime(cloud_time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
            local_time = datetime.datetime.fromtimestamp(os.path.getmtime(filename))
            local_tz = time.timezone - 3600

            time_delta = cloud_time - local_time

            if sys.version_info < (2, 7, 0):
                # as specified in Python docs
                time_delta_secs = (time_delta.microseconds + (time_delta.seconds + time_delta.days * 24 * 3600) * 10 ** 6) / 10 ** 6
            else:
                time_delta_secs = time_delta.total_seconds()

            time_diff = time_delta_secs - local_tz

        if int(local_size) != int(cloud_size):
            print "UPPPP SIZE"
            return True

        if not self.skip_time_check and time_diff < -30:
            print "UPPPP TIME", self.skip_time_check
            return True
        else:
            print "NO UP"
            return False

    def convert_win_path(self, filename):
        if sys.platform.startswith('win'):
            exp_file = os.path.abspath(os.path.expandvars(filename))
            unix_file = os.path.normpath(exp_file).replace('\\', "/")
            for i in submit_settings.DRIVE_MAPS:
                unix_file = unix_file.lstrip(i)
        else:
            unix_file = filename
        return unix_file

    def submit_request_api(self, filename, bucket_name, object_name):
        media = MediaFileUpload(filename, submit_settings.DEFAULT_MIMETYPE)
        req = self.service.objects().insert(bucket=bucket_name, name=object_name, media_body=media)
        self.run_request(req)

    def does_local_exist(self, filename):
        files = glob.glob(filename)
        return len(files) > 0

    def submit_request(self, filename, cloud_dir, max_tries=5):
        cmd = self.build_copy_cmd(filename, cloud_dir)
        tries = 1
        while tries < max_tries:
            results, out, err = self.call_cmd(cmd)
            if results.returncode == 0:
                tries = 5
            else:
                tries += 1
                time.sleep(tries * 3)

        if results.returncode != 0:
            raise IOError("Could not Upload file! \n%s\n%s" % (out, err))

    def build_copy_cmd(self, local_file, cloud_dir):
        cmd = '%s -m ' % self._storage_cmd
        if os.path.isdir(local_file):
            cmd += "rsync -r "
        else:
            cmd += "cp "
        cmd += "%s %s " % (local_file, cloud_dir)
        return cmd

    def call_cmd(self, cmd):
        results = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = results.communicate()
        return results, out, err

    def submit_upload(self, f, unix_file):
        bucket_name = "%s" % submit_settings._BUCKET_NAME
        object_name = "%s%s" % (submit_settings._UPLOAD_POINT, unix_file)
        if os.path.isdir(f):
            unix_dir = "%s%s/" % (submit_settings._CLOUD_ROOT, unix_file)
        else:
            unix_dir = "%s%s/" % (submit_settings._CLOUD_ROOT, os.path.dirname(unix_file))
        print "Uploading %s to %s" % (f, unix_dir)
        if self.does_local_exist(f):
            self.submit_request(f, unix_dir)
        else:
            print "Could not locate files on local drive: %s" % f
            return False
        # upload_files.append(f)
        print("Uploaded %s" % f)
        return True

    def run_uploads(self):
        upload_files = []
        upload_file_name = None
        # pool = multiprocessing.Pool(processes=4)
        for filename in self.upload_files:

            # Handle frame padding files.
            filename = re.sub("%0[0-9]d", '*', filename)
            filename = re.sub("#+", '*', filename)

            if os.path.isdir(filename):
                glob_files = [filename]
            else:
                glob_files = glob.glob(filename)

            if len(glob_files) == 0:
                print "No files located locally, skipping. %s" % filename

            elif len(glob_files) < 20:
                for f in glob_files:
                    print "Checking, %s" % f
                    # Sanitize the path for linux and cloud storage
                    unix_file = self.convert_win_path(f)
                    if not unix_file.startswith('/'):
                        print('All files should be passed in as absolute linux paths!')
                        raise IOError('File does not start at root mount "/", %s' % f)
                    if self.is_upload_needed(f, unix_file) or self.force:
                        if self.submit_upload(f, unix_file):
                            upload_files.append(f)
                    else:
                        print "Skipping, upload not needed."

            else:
                # Only check the first/mid/last frames
                print "Looking at sequence, %s" % filename
                files_to_check = [glob_files[0], glob_files[len(glob_files) / 2], glob_files[-1]]

                upload_needed = False

                for f in files_to_check:
                    print "Checking, %s" % f
                    unix_f = self.convert_win_path(f)
                    if self.is_upload_needed(f, unix_f) or self.force:
                        print "  Found mismatch: %s" % unix_f
                        upload_needed = True
                        break

                if upload_needed:
                    f = filename
                    unix_file = self.convert_win_path(f)
                    if not unix_file.startswith('/'):
                        print('All files should be passed in as absolute linux paths!')
                        raise IOError('File does not start at root mount "/", %s' % f)

                    if self.submit_upload(f, unix_file):
                        upload_files.append(f)
                else:
                    print "Skipping, upload not needed."

                # pool.apply_async(self.submit_request, args=(filename, unix_dir))
                # Upload the file to cloud storage
                # media = MediaFileUpload(filename, chunksize=submit_settings.CHUNKSIZE, resumable=True)
                # if not media.mimetype():
                #    media = MediaFileUpload(filename, submit_settings.DEFAULT_MIMETYPE, resumable=True)
                # media = MediaFileUpload(filename, submit_settings.DEFAULT_MIMETYPE)
                # req = self.service.objects().insert(bucket=bucket_name, name=object_name, media_body=media)

                # pool.apply_async(self.submit_request, args=(filename, bucket_name, object_name))
                # pool.apply_async(self.run_request, args=(req,))
                # resp = self.run_request(req)
                # resp = self.chunk_request(req)

        # pool.close()
        # pool.join()

        if len(upload_files) > 0:
            # Create a tmp file to keep track of what was uploaded.
            # This file gets passed to Job submission.

            upload_file_name = "%s_upload" % int(self.timeid)
            tmp_file = '%s/%s' % (os.environ['TEMP'], upload_file_name)
            try:
                with open(tmp_file, 'w') as temp:
                    temp.write(",".join(upload_files))
            except IOError, e:
                print("Could not write tmp file! check permissions. %s" % tmp_file)
                raise e

            bucket_name = "%s" % submit_settings._BUCKET_NAME
            upload_file_name = "%s_upload" % int(time.time())
            object_name = "%s/%s" % (submit_settings._UPLOAD_FILE_POINT, upload_file_name)
            media = MediaFileUpload(tmp_file, chunksize=submit_settings.CHUNKSIZE, resumable=True)
            if not media.mimetype():
                media = MediaFileUpload(tmp_file, submit_settings.DEFAULT_MIMETYPE, resumable=True)
            req = self.service.objects().insert(bucket=bucket_name, name=object_name, media_body=media)
            resp = self.run_request(req)
            os.remove(tmp_file)

            return object_name





class BadArgumentError(ValueError):
    pass

if __name__ == '__main__':
    submitter = Submit()
    submitter.main()

