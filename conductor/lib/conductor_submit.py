#!/usr/bin/env python

""" Command Line General Submitter for sending jobs and uploads to Conductor

"""


import base64
import os
import sys
import re
import glob
import time
import argparse
import hashlib
import httplib2
import urllib
import urllib2
import json
import random
import datetime
import tempfile
import getpass
import subprocess
import multiprocessing
import threading
import random
import math
import traceback

# TODO: test removal of apiclient and oauth
from apiclient import discovery
from apiclient.http import MediaFileUpload
from apiclient.errors import HttpError
from oauth2client import file as oauthfile
from oauth2client import client
from oauth2client import tools
from multiprocessing import Process, Queue


# from conductor
from lib.common import logging, retry, Config
from httplib2 import Http

_this_dir = os.path.dirname(os.path.realpath(__file__))

class Submit():
    """ Conductor Submission
    Command Line Usage:
        $ python conductor_submit.py --upload_file /path/to/upload_file.txt --frames 1001-1100 --cmd

    Help:
        $ python conductor_submit.py -h
    """
    def __init__(self, args):
        self.timeid = int(time.time())
        self.consume_args(args)

    @classmethod
    def from_commmand_line(cls):
        args = cls._parseArgs()
        return cls(vars(args))  # convert the Namespace object to a dictionary

    def consume_args(self, args):
        self.raw_command = args.get('cmd')
        self.user = args.get('user')
        self.frames = args.get('frames')
        self.resource = args.get('resource')
        self.cores = args.get('cores')
        self.priority = args.get('priority')
        self.upload_dep = args.get('upload_dependent')
        self.output_path = args.get('output_path')
        self.upload_file = args.get('upload_file')
        self.upload_paths = args.get('upload_paths')
        self.upload_only = args.get('upload_only')
        self.postcmd = args.get('postcmd')
        self.skip_time_check = args.get('skip_time_check')
        self.force = args.get('force')

        # TODO: switch this behavior to use file size plus md5 instead
        # For now always default nuke uploads to skip time check
        if self.upload_only or "nuke-render" in self.raw_command:
            self.skip_time_check = True

        if self.upload_paths is None:
            self.upload_paths = []

    @classmethod
    def _parseArgs(cls):
        parser = argparse.ArgumentParser(description=cls.__doc__,
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
        parser.add_argument("--cores",
            help="Number of cores that this job should run on",
            type=int,
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
            print "self.upload_file is " + self.upload_file
            with open(self.upload_file, 'r') as f:
                print 'opening file'
                contents = f.read()
                print "contents is '%s'" % contents
            print "contents is '%s'" % contents
            for file_name in contents.split(','):
                print "file_name is '%s'" % str(file_name)
                # TODO:
                files.extend(Uploader().get_children(file_name))
                # uploader_args = {'url': 'http://test.conductor.io:8080' }
                # files.extend(Uploader(uploader_args).get_children(file_name))

        return files


    def get_token(self):
        token_path = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "auth/CONDUCTOR_TOKEN.pem"))
        if not os.path.exists(token_path):
            raise IOError("Could not locate .pem file: %s" % token_path)
        with open(token_path, 'r') as f:
            user = f.read()
        userpass = "%s:unused" % user.rstrip()
        return userpass

    def send_job(self, upload_files=None):
        userpass = self.get_token()
        if self.raw_command and self.frames:
            url = "jobs/"
            if not self.resource:
                self.resource = "default"
            if not self.cores:
                self.cores = 16

            resource_tag = "%s-%s" % (self.cores, self.resource.lower())

            submit_dict = {'owner':self.user,
                           'resource':resource_tag,
                           'frame_range':self.frames,
                           'command':self.raw_command,
                           'instance_type':'n1-standard-16'}
            if upload_files:
                submit_dict['upload_files'] = ','.join(upload_files)
            if self.priority:
                submit_dict['priority'] = self.priority
            if self.upload_dep:
                submit_dict['dependent'] = self.upload_dep
            if self.postcmd:
                submit_dict['postcmd'] = self.postcmd
            if self.output_path:
                submit_dict['output_path'] = self.output_path
        elif self.upload_only and upload_files:
            url = "jobs/"
            submit_dict = {'upload_files': ','.join(upload_files),
                           'owner': self.user,
                           'frame_range':"x",
                           'command':'upload only',
                           'instance_type':'n1-standard-1'}
        else:
            raise BadArgumentError('The supplied arguments could not submit a valid request.')

        json_dict = json.dumps(submit_dict)
        conductor_url = "https://riotgames-dot-atomic-light-001.appspot.com/%s" % url
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
        # TODO: remove upload_paths
        if self.upload_file or self.upload_paths:
            upload_files = self.get_upload_files()
            uploads = Uploads(upload_files, self.timeid, self.skip_time_check, force=self.force)

            # TODO
            uploader = Uploader()

            # uploader_args = {'url': 'http://test.conductor.io:8080' }
            # uploader = Uploader(uploader_args)

            uploaded_files = uploader.run_uploads(upload_files)

            # upload_file = uploads.run_uploads()
            # if upload_file:
            #     print upload_file
            # else:
            #     print "Upload Not Needed."
            #     if self.upload_only:
            #         return

        # Submit the job to conductor
        resp = self.send_job(upload_files = uploaded_files)
        print resp
        return resp


class Uploads():
    """ Manages Uploads from Local File System to Conductor """
    def __init__(self, upload_files, timeid, skip_time_check=False, force=False):
        self._secret_key = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "auth/atomic-light-001.p12"))
        self._gcloud_cmd = "gcloud auth activate-service-account %s --key-file %s --project %s" % (
                                submit_settings._SERVICE_ACCOUNT_EMAIL, self._secret_key, submit_settings._CLOUD_PROJECT)
        self._storage_cmd = "gsutil"
        self.timeid = timeid
        self.upload_files = upload_files
        self.skip_time_check = skip_time_check
        self.force = force


    def run_uploads(self):
        upload_files = []
        upload_file_name = None
        # pool = multiprocessing.Pool(processes=4)
        for filename in self.upload_files:

            print 'filename is ' + filename
            next

            # Handle frame padding files.
            filename = re.sub("%0[0-9]d", '*', filename)
            filename = re.sub("#+", '*', filename)

            if os.path.isdir(filename):
                glob_files = [filename]
            else:
                glob_files = glob.glob(filename)







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


class Uploader():
    def __init__(self,args=None):

        print 'creating new iploader'
        self.userpass = None
        self.get_token()

    def get_children(self,path):
        path = path.strip()
        if os.path.isfile(path):
            logging.debug("path %s is a file" % path)
            return [self.clean_filename(path)]
        if os.path.isdir(path):
            logging.debug("path %s is a dir" % path)
            file_list = []
            for root, dirs, files in os.walk(path,followlinks=True):
                for name in files:
                    file_list.append(self.clean_filename(os.path.join(root,name)))
            return file_list
        else:
            logging.debug("path %s does not make sense" % path)
            raise ValueError

    def get_upload_url(self,filename):
        app_url = config.config['url'] + '/api/files/get_upload_url'
        # TODO: need to pass md5 and filename
        params = {
            'filename': filename,
            'md5': self.get_base64_md5(filename)
        }
        logging.debug('app_url is %s' % app_url)
        logging.debug('params are %s' % params)
        upload_url = self.send_job(url=app_url,params=params)
        return upload_url


    def send_job(self,headers=None,url=None,params=None):
        if headers is None:
            headers = {'Content-Type':'application/json'}


        if url is None:
            conductor_url = config.config['url']
        else:
            conductor_url = url

        if params is not None:
            # append trailing slash if not present
            # if url[-1] != '/':
            #     url += '/'
            conductor_url += '?'
            conductor_url += urllib.urlencode(params)


        userpass = self.get_token()

        submit_dict = {}
        json_dict = json.dumps(submit_dict)


        # conductor_url = url
        logging.debug('conductor_url is %s' % conductor_url)
        password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(None, conductor_url, userpass.split(':')[0], 'unused')
        auth = urllib2.HTTPBasicAuthHandler(password_manager)
        opener = urllib2.build_opener(auth)
        urllib2.install_opener(opener)


        logging.debug('conductor_url is: %s' % conductor_url)
        logging.debug('headers are: %s' % headers)
        req = urllib2.Request(conductor_url,
                            headers=headers,
                            )
                            # data=json_dict)
        logging.debug('request is %s' % req)



        logging.debug('trying to connect to app')
        handler = retry(lambda: urllib2.urlopen(req))

        f = handler.read()
        logging.debug('f is: %s' %f)
        return f

    def get_md5(self,file_path, blocksize=65536):
        logging.debug('trying to open %s' % file_path)
        logging.debug('file_path.__class__ %s' % file_path.__class__)
        hasher = hashlib.md5()
        afile = open(file_path,'rb')
        buf = afile.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(blocksize)
        return hasher.digest()


    def get_base64_md5(self,*args,**kwargs):
        md5 = self.get_md5(*args)
        # logging.debug('md5 is %s' % md5)
        b64 = base64.b64encode(md5)
        logging.debug('b64 is %s' % b64)
        return b64


    def clean_filename(self,filename):
        # Handle frame padding files.
        filename = re.sub("%0[0-9]d", '*', filename)
        filename = re.sub("#+", '*', filename)
        filename = self.convert_win_path(filename)
        print "filename is " + filename
        if not filename.startswith('/'):
            print('All files should be passed in as absolute linux paths!')
            raise IOError('File does not start at root mount "/", %s' % filename)
        return filename

    def convert_win_path(self, filename):
        if sys.platform.startswith('win'):
            exp_file = os.path.abspath(os.path.expandvars(filename))
            unix_file = os.path.normpath(exp_file).replace('\\', "/")
            for i in submit_settings.DRIVE_MAPS:
                unix_file = unix_file.lstrip(i)
        else:
            unix_file = filename
        return unix_file


    def get_token(self):
        if self.userpass != None:
            return self.userpass
        token_path = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "auth/CONDUCTOR_TOKEN.pem"))
        if not os.path.exists(token_path):
            raise IOError("Could not locate .pem file: %s" % token_path)
        with open(token_path, 'r') as f:
            user = f.read()
        userpass = "%s:unused" % user.rstrip()
        self.userpass = userpass
        return userpass


    def run_uploads(self,file_list):

        process_count = config.config['thread_count']

        uploaded_queue = Queue()

        upload_queue = Queue()
        for file in file_list:
            logging.debug('adding %s to queue' % file)
            upload_queue.put(file)

        threads = []
        for n in range(process_count):
            thread = threading.Thread(target=self.upload_file, args = (upload_queue, uploaded_queue))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()


        uploaded_list = []
        while not uploaded_queue.empty():
            uploaded_list.append(uploaded_queue.get())

        return uploaded_list


    def upload_file(self,upload_queue, uploaded_queue):
    # def upload_file(self,filename):
        # time.sleep(random.random())
        logging.debug('entering upload_file')
        filename = upload_queue.get()
        logging.debug('trying to upload %s' % filename)
        upload_url = self.get_upload_url(filename)
        logging.debug("upload url is '%s'" % upload_url)
        if upload_url is not '':
            uploaded_queue.put(filename)
            logging.debug('uploading file %s' % filename)
            # Add retries
            resp, content = retry(lambda: self.do_upload(upload_url,"POST", open(filename,'rb')))
            logging.debug('finished uploading %s' % filename)

        if upload_queue.empty():
            Logging.debug('upload_queue is empty')
            return None
        else:
            logging.debug('upload_queue is not empty')
            self.upload_file(upload_queue)



    def do_upload(self,upload_url,http_verb,buffer):
        h = Http()
        resp, content = h.request(upload_url,http_verb, buffer)
        return resp, content



class BadArgumentError(ValueError):
    pass

config = Config()

if __name__ == '__main__':
    submission = Submit.from_commmand_line()
    submission.main()
