#!/usr/bin/env python

""" Command Line General Submitter for sending jobs and uploads to Conductor

"""


import base64
import os
import sys
import re
import time
import json
import argparse
import itertools
import hashlib
import urllib
import urllib2
import urlparse
import getpass
import threading
import multiprocessing
import Queue as queue_exception

# from conductor
import conductor

from conductor.lib.common import retry
from httplib2 import Http


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
        print "itit Submit"
        self.timeid = int(time.time())
        self.consume_args(args)
        self.validate_args()
        print "Consumed args"

    @classmethod
    def from_commmand_line(cls):
        args = cls._parseArgs()
        return cls(vars(args))  # convert the Namespace object to a dictionary

    def consume_args(self, args):
        self.raw_command = args.get('cmd')
        self.user = args.get('user') or getpass.getuser()
        self.frames = args.get('frames')
        self.upload_dep = args.get('upload_dependent')
        self.output_path = args.get('output_path')
        self.upload_file = args.get('upload_file')
        self.upload_only = args.get('upload_only')
        self.postcmd = args.get('postcmd')
        self.skip_time_check = args.get('skip_time_check') or False
        self.force = args.get('force')

        # Apply client config values in cases where arguments have not been passed in
        self.cores = args.get('cores', CONFIG["instance_cores"])
        self.resource = args.get('resource', CONFIG["resource"])
        self.priority = args.get('priority', CONFIG["priority"])
        self.upload_paths = args.get('upload_paths', [])


        # TODO: switch this behavior to use file size plus md5 instead
        # For now always default nuke uploads to skip time check
        if self.upload_only or "nuke-render" in self.raw_command:
            self.skip_time_check = True



    def validate_args(self):
        '''
        Ensure that the combination of arugments don't result in an invalid job/request
        '''
        # TODO: Clean this shit up
        if self.raw_command and self.frames:
            pass

        elif self.upload_only and (self.upload_file or self.upload_paths):
            pass

        else:
            raise BadArgumentError('The supplied arguments could not submit a valid request.')



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
            nargs="*")  # TODO(lws): ensure that this return an empty list if not specified
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

#
#     def get_upload_files(self):
#         """ When given an upload file, return a list of files.
#             Expects a file containing string absolute file paths,
#             seperated by commas.
#         """
#         files = []
#
#         for file_name in self.upload_paths:
#             print "file_name is '%s'" % str(file_name)
#             # TODO:
#             files.extend(Uploader().get_children(file_name))
#
#         return files


#     def get_token(self):
#         token_path = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "auth/CONDUCTOR_TOKEN.pem"))
#         if not os.path.exists(token_path):
#             raise IOError("Could not locate .pem file: %s" % token_path)
#         with open(token_path, 'r') as f:
#             user = f.read()
#         userpass = "%s:unused" % user.rstrip()
#         return userpass

    def send_job(self, upload_files=None):
        '''
        Construct args for two different cases:
            - upload_only
            - running an actual command (cmd)
        '''
        logger.debug("upload_files: %s", upload_files)

        submit_dict = {'owner':self.user}
        if upload_files:
            submit_dict['upload_files'] = ','.join(upload_files)

        if self.upload_only:
            # If there are not files to upload, then simulate a response dictrioary
            # and return a "no work to do" message
            if not upload_files:
                response_dict = {"message": "No files to upload"}
                response_code = 204
                return response_dict, response_code

            submit_dict.update({'frame_range':"x",
                                'command':'upload only',
                                'instance_type':'n1-standard-1'})
        else:

            submit_dict.update({'resource':self.resource,
                                'frame_range':self.frames,
                                'command':self.raw_command,
                                'cores':self.cores})

            if self.priority:
                submit_dict['priority'] = self.priority
            if self.upload_dep:
                submit_dict['dependent'] = self.upload_dep
            if self.postcmd:
                submit_dict['postcmd'] = self.postcmd
            if self.output_path:
                submit_dict['output_path'] = self.output_path

        logger.debug("send_job JOB ARGS:")
        for arg_name, arg_value in sorted(submit_dict.iteritems()):
            logger.debug("%s: %s", arg_name, arg_value)


        # TODO: verify that the response request is valid
        response_dict, response_code = make_request(uri_path="jobs/", data=json.dumps(submit_dict))
        return response_dict, response_code


    def main(self):
        upload_files = self.get_upload_files()

        uploader = Uploader()
        uploaded_files = uploader.run_uploads(upload_files)

        # Submit the job to conductor
        response_string, response_code = self.send_job(upload_files=uploaded_files)
        return json.loads(response_string), response_code


    def get_upload_files(self):
        '''
        Resolve the upload_paths and upload_file arguments to return a single list
        of paths to upload
        '''
        filepaths = []
        if self.upload_file:

            # ## Resolve the "upload_file" arg
            logger.debug("self.upload_file is %s", self.upload_file)

            with open(self.upload_file, 'r') as file_:
                logger.debug('opening file')
                contents = file_.read()
                file_list = contents.split(",")

            # call get_children for each file in the file list
            for filepath in file_list:
                filepaths += Uploader().get_children(filepath)

        if self.upload_paths:
            for filepath in self.upload_paths:
                children = Uploader().get_children(filepath)
                filepaths += children


        # merge the paths from both upload file arguments
        return filepaths

class Uploader():
    def __init__(self, args=None):
        logger.debug("Uploader.__init__")
        authorize_urllib()

    def get_children(self, path):
        path = path.strip()
        if os.path.isfile(path):
            logger.debug("path %s is a file" % path)
            return [self.clean_filename(path)]
        if os.path.isdir(path):
            logger.debug("path %s is a dir" % path)

            file_list = []
            for root, _, files in os.walk(path, followlinks=True):
                for name in files:
                    file_list.append(self.clean_filename(os.path.join(root, name)))
            return file_list
        else:
            logger.debug("path %s does not make sense" % path)
            raise ValueError


    def get_upload_url(self, filename):

        uri_path = '/api/files/get_upload_url'
        # TODO: need to pass md5 and filename
        params = {
            'filename': filename,
            'md5': self.get_base64_md5(filename)
        }
        logger.debug('params are %s' % params)
        response_string, response_code = make_request(uri_path=uri_path, params=params)
        # TODO: validate that no error occured via error code
        return response_string

    def get_md5(self, file_path, blocksize=65536):
        logger.debug('trying to open %s' % file_path)
        logger.debug('file_path.__class__ %s' % file_path.__class__)

        hasher = hashlib.md5()
        afile = open(file_path, 'rb')
        buf = afile.read(blocksize)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(blocksize)
        return hasher.digest()


    def get_base64_md5(self, *args, **kwargs):
        md5 = self.get_md5(*args)
        b64 = base64.b64encode(md5)
        logger.debug('b64 is %s' % b64)
        return b64


    def clean_filename(self, filename):
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


#     def get_token(self):
#         if self.userpass != None:
#             return self.userpass
#         token_path = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "auth/CONDUCTOR_TOKEN.pem"))
#         if not os.path.exists(token_path):
#             raise IOError("Could not locate .pem file: %s" % token_path)
#         with open(token_path, 'r') as f:
#             user = f.read()
#         userpass = "%s:unused" % user.rstrip()
#         self.userpass = userpass
#         return userpass


    def run_uploads(self, file_list):
        if not file_list:
            logger.debug("No files to upload. Skipping run_uploads")
            return []

        process_count = CONFIG['thread_count']
        uploaded_queue = multiprocessing.Queue()
        upload_queue = multiprocessing.Queue()
        for upload_file in file_list:
            logger.debug('adding %s to queue' % upload_file)
            upload_queue.put(upload_file)

        threads = []
        for n in range(process_count):

            thread = threading.Thread(target=self.upload_file, args=(upload_queue, uploaded_queue))

            thread.start()
            threads.append(thread)

        for idx, thread in enumerate(threads):
            print 'waiting for thread: %s' % idx
            thread.join()

        print 'done with threading stuff'
        uploaded_list = []
        while not uploaded_queue.empty():
            uploaded_list.append(uploaded_queue.get())

        return uploaded_list


    def upload_file(self, upload_queue, uploaded_queue):
        logger.debug('entering upload_file')
        try:
            filename = upload_queue.get(block=False)
        except queue_exception.Empty:
            print 'queue is empty, caught EMPTY'
            return

        logger.debug('trying to upload %s' % filename)
        upload_url = self.get_upload_url(filename)
        logger.debug("upload url is '%s'" % upload_url)
        if upload_url is not '':
            uploaded_queue.put(filename)
            logger.debug('uploading file %s' % filename)
            # Add retries
            resp, content = retry(lambda: self.do_upload(upload_url, "POST", open(filename, 'rb')))
            logger.debug('finished uploading %s' % filename)

        if upload_queue.empty():
            print('upload_queue is empty')
            return None
        else:
            logger.debug('upload_queue is not empty')

            self.upload_file(upload_queue, uploaded_queue)


        return


    def do_upload(self, upload_url, http_verb, upload_buffer):
        h = Http()
        resp, content = h.request(upload_url, http_verb, upload_buffer)
        return resp, content


def get_token():
    # TODO: Take CONDUCTOR_TOKEN.pem from config
    token_path = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "auth/CONDUCTOR_TOKEN.pem"))
    if not os.path.exists(token_path):
        raise IOError("Could not locate .pem file: %s" % token_path)
    with open(token_path, 'r') as f:
        user = f.read()
    userpass = "%s:unused" % user.rstrip()
    return userpass

def authorize_urllib():
    '''
    This is crazy magic that's apparently ok
    '''
    token = get_token()
    password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, CONFIG['url'], token.split(':')[0], 'unused')
    auth = urllib2.HTTPBasicAuthHandler(password_manager)
    opener = urllib2.build_opener(auth)
    urllib2.install_opener(opener)


def make_request(uri_path="/", headers=None, params=None, data=None, verb=None):
    '''
    verb: PUT, POST, GET, DELETE, HEAD
    '''
    # TODO: set Content Type to json if data arg
    if not headers:
        headers = {'Content-Type':'application/json'}
    logger.debug('headers are: %s' % headers)

    # Construct URL
    conductor_url = urlparse.urljoin(CONFIG['url'], uri_path)
    print 'conductor_url', conductor_url, type(conductor_url)
    if params:
        conductor_url += '?'
        conductor_url += urllib.urlencode(params)
    logger.debug('conductor_url is %s', conductor_url)

    req = urllib2.Request(conductor_url, headers=headers, data=data)
    if verb:
        req.get_method = lambda: verb
    logger.debug('request is %s' % req)

    logger.debug('trying to connect to app')
    handler = retry(lambda: urllib2.urlopen(req))
    response_string = handler.read()
    response_code = handler.getcode()
    logger.debug('response_code: %s', response_code)
    logger.debug('response_string is: %s' % response_string)
    return response_string, response_code


class BadArgumentError(ValueError):
    pass


if __name__ == '__main__':
    submission = Submit.from_commmand_line()
    submission.main()
