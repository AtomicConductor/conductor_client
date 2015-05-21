#!/usr/bin/env python

""" Command Line General Submitter for sending jobs and uploads to Conductor

"""


import os
import sys
import time
import json
import argparse
import itertools
import getpass
import imp

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import conductor
import conductor.setup
from conductor.lib import common, file_utils, api_client
from httplib2 import Http


logger = conductor.setup.logger
CONFIG = conductor.setup.CONFIG

class Submit():
    """ Conductor Submission
    Command Line Usage:
        $ python conductor_submit.py --upload_file /path/to/upload_file.txt --frames 1001-1100 --cmd

    Help:
        $ python conductor_submit.py -h
    """
    def __init__(self, args):
        logger.debug("itit Submit")
        self.timeid = int(time.time())
        self.consume_args(args)
        self.validate_args()
        logger.debug("Consumed args")
        self.api_client = conductor.lib.api_client.ApiClient()

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

        uploader = conductor.lib.uploader.Uploader()
        uploaded_files = uploader.run_uploads(upload_files)

        # Submit the job to conductor
        response_string, response_code = self.send_job(upload_files=uploaded_files)
        return json.loads(response_string), response_code


    def get_upload_files(self):
        '''
        Resolve the "upload_paths" and "upload_file" arguments to return a single list
        of paths that will get uploaded to the cloud.
        '''
        # begin a list of "raw" filepaths that will need to be processed (starting with the self.upload_paths)
        raw_filepaths = list(self.upload_paths)

        # if an upload file as been provided, parse it and add it's paths to the "raw" filepaths
        if self.upload_file:
            logger.debug("self.upload_file is %s", self.upload_file)
            upload_files = self. parse_upload_file(self.upload_file)
            raw_filepaths.extend(upload_files)

        # Process the raw filepaths (to account for directories, image sequences, formatting, etc)
        return file_utils.process_upload_filepaths(raw_filepaths)


    def parse_upload_file(self,upload_filepath):
        '''
        Parse the given filepath for paths that are separated by commas, returning
        a list of these paths
        '''
        with open(upload_filepath, 'r') as file_:
            logger.debug('opening file')
            contents = file_.read()
        return [path.strip() for path in contents.split(",")]


class BadArgumentError(ValueError):
    pass


if __name__ == '__main__':
    submission = Submit.from_commmand_line()
    submission.main()
