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


# from conductor
import conductor
from conductor.lib.common import retry
from httplib2 import Http

_this_dir = os.path.dirname(os.path.realpath(__file__))
logger = conductor.logger
CONFIG = conductor.CONFIG

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
            with open(self.upload_file, 'r') as f:
                print 'opening file'
                contents = f.read()
                print "contents is '%s'" % contents
            print "contents is '%s'" % contents
            for file_name in contents.split(','):
                print "file_name is '%s'" % str(file_name)
                # TODO:
                files.extend(Uploader().get_children(file_name))

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
        logger.debug("Entering Submit.main")
        uploaded_files = None
        # TODO: fix/test upload_paths
        if self.upload_file or self.upload_paths:
            logger.debug("Running upload process")
            upload_files = self.get_upload_files()
            uploader = Uploader()
            uploaded_files = uploader.run_uploads(upload_files)
        else:
            logger.debug("No upload files specified")

        # Submit the job to conductor
        resp = self.send_job(upload_files = uploaded_files)
        logger.info("RESPONSE DICTIONARY: %s" % resp)
        return resp


class Uploader():
    def __init__(self,args=None):
        self.userpass = None
        self.get_token()


    def get_children(self,path):
        path = path.strip()
        if os.path.isfile(path):
            logger.debug("path %s is a file" % path)
            return [self.clean_filename(path)]
        if os.path.isdir(path):
            logger.debug("path %s is a dir" % path)
            file_list = []
            for root, dirs, files in os.walk(path,followlinks=True):
                for name in files:
                    file_list.append(self.clean_filename(os.path.join(root,name)))
            return file_list
        else:
            logger.debug("path %s does not make sense" % path)
            raise ValueError


    def get_upload_url(self,filename):
        app_url = CONFIG['url'] + '/api/files/get_upload_url'
        # TODO: need to pass md5 and filename
        params = {
            'filename': filename,
            'md5': self.get_base64_md5(filename)
        }
        logger.debug('app_url is %s' % app_url)
        logger.debug('params are %s' % params)
        upload_url = self.send_job(url=app_url,params=params)
        return upload_url


    def send_job(self,headers=None,url=None,params=None):
        if headers is None:
            headers = {'Content-Type':'application/json'}

        conductor_url = url or CONFIG['url']

        if params is not None:
            # append trailing slash if not present
            # if url[-1] != '/':
            #     url += '/'
            conductor_url += '?'
            conductor_url += urllib.urlencode(params)


        userpass = self.get_token()
        submit_dict = {}
        json_dict = json.dumps(submit_dict)

        logger.debug('conductor_url is %s' % conductor_url)
        password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(None, conductor_url, userpass.split(':')[0], 'unused')
        auth = urllib2.HTTPBasicAuthHandler(password_manager)
        opener = urllib2.build_opener(auth)
        urllib2.install_opener(opener)
        logger.debug('conductor_url is: %s' % conductor_url)
        logger.debug('headers are: %s' % headers)
        req = urllib2.Request(conductor_url,
                            headers=headers,
                            )
        logger.debug('request is %s' % req)
        logger.debug('trying to connect to app')
        handler = retry(lambda: urllib2.urlopen(req))
        f = handler.read()
        logger.debug('f is: %s' %f)
        return f


    def get_md5(self,file_path, blocksize=65536):
        logger.debug('trying to open %s' % file_path)
        logger.debug('file_path.__class__ %s' % file_path.__class__)
        hasher = hashlib.md5()
        afile = open(file_path,'rb')
        buf = afile.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(blocksize)
        return hasher.digest()


    def get_base64_md5(self,*args,**kwargs):
        md5 = self.get_md5(*args)
        # logger.debug('md5 is %s' % md5)
        b64 = base64.b64encode(md5)
        logger.debug('b64 is %s' % b64)
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
        process_count = CONFIG['thread_count']
        uploaded_queue = Queue()
        upload_queue = Queue()
        for file in file_list:
            logger.debug('adding %s to queue' % file)
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
        logger.debug('entering upload_file')
        filename = upload_queue.get()
        logger.debug('trying to upload %s' % filename)
        upload_url = self.get_upload_url(filename)
        logger.debug("upload url is '%s'" % upload_url)
        if upload_url is not '':
            uploaded_queue.put(filename)
            logger.debug('uploading file %s' % filename)
            # Add retries
            resp, content = retry(lambda: self.do_upload(upload_url,"POST", open(filename,'rb')))
            logger.debug('finished uploading %s' % filename)

        if upload_queue.empty():
            Logging.debug('upload_queue is empty')
            return None
        else:
            logger.debug('upload_queue is not empty')
            self.upload_file(upload_queue)


    def do_upload(self,upload_url,http_verb,buffer):
        h = Http()
        resp, content = h.request(upload_url,http_verb, buffer)
        return resp, content


class BadArgumentError(ValueError):
    pass

if __name__ == '__main__':
    submission = Submit.from_commmand_line()
    submission.main()
