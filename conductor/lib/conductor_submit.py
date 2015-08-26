#!/usr/bin/env python

""" Command Line General Submitter for sending jobs and uploads to Conductor

"""


import getpass
import imp
import json
import os
import sys
import time

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


import conductor.setup
from conductor.lib import file_utils, api_client, uploader, common


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
        logger.debug("Init Submit")
        self.timeid = int(time.time())
        self.consume_args(args)
        self.validate_args()
        self.api_client = api_client.ApiClient()


    def consume_args(self, args):
        self.raw_command = args.get('cmd') or ''
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

        # Get any upload files/dirs listed in the config.yml
        self.upload_paths = CONFIG.get('upload_paths', [])
        assert isinstance(self.upload_paths, list), "Not a list: %s" % self.upload_paths
        # Append any upload files/dirs specified via the command line
        self.upload_paths.extend(args.get('upload_paths'))
        logger.debug("Got upload_paths: %s" % (self.upload_paths))

        #  Get any environment variable settings from config.yml
        self.environment = CONFIG.get("environment", {})
        assert isinstance(self.environment, dict), "Not a dictionary: %s" % self.environment
        # Then override any that were specified in the command line
        self.environment.update(args.get('env', {}))
        logger.debug("Got environment: %s" % (self.environment))

        local_upload = args.get('local_upload')
        # If the local_upload arge was specified by the user (i.e if it's not None), the use it
        if local_upload != None:
            self.local_upload = local_upload
        # Otherwise use the value in the config
        else:
            self.local_upload = CONFIG['local_upload']

        # For now always default nuke uploads to skip time check
        if self.upload_only or "nuke-render" in self.raw_command:
            self.skip_time_check = True

        self.location = args.get('location') or CONFIG.get("location")
        self.docker_image = args.get('docker_image') or CONFIG.get("docker_image")
        logger.debug("Consumed args")


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

    def send_job(self, upload_files=None):
        '''
        Construct args for two different cases:
            - upload_only
            - running an actual command (cmd)
        '''
        logger.debug("upload_files: %s", upload_files)

        submit_dict = {'owner':self.user}
        submit_dict['location'] = self.location
        submit_dict['docker_image'] = self.docker_image
        submit_dict['local_upload'] = self.local_upload

        if upload_files:
            upload_file_dict = {}
            for upload_file in upload_files:
                upload_file_dict[upload_file] = common.get_base64_md5(upload_file)
            submit_dict['upload_files'] = upload_file_dict

        if self.upload_only:
            # If there are not files to upload, then simulate a response string
            # and return a "no work to do" message
            if not upload_files:
                response = json.dumps({"message": "No files to upload", "jobid":None})
                response_code = 204
                return response, response_code

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
            if self.environment:
                submit_dict['environment'] = self.environment


        logger.debug("send_job JOB ARGS:")
        for arg_name, arg_value in sorted(submit_dict.iteritems()):
            logger.debug("%s: %s", arg_name, arg_value)


        response, response_code = self.api_client.make_request(uri_path="jobs/", data=json.dumps(submit_dict))
        if response_code not in [201, 204]:
            raise Exception("Submitting Upload job failed: Error %s ...\n%s" % (response_code, response))
        return response, response_code


    def main(self):
        upload_files = self.get_upload_files()
        if self.local_upload:
            uploader_ = uploader.Uploader()
            upload_error_message = uploader_.handle_upload_response(upload_files)
            if upload_error_message:
                raise Exception("Could not upload files:\n%s" % upload_error_message)
        # Submit the job to conductor
        response, response_code = self.send_job(upload_files=upload_files)
        return json.loads(response), response_code

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
            upload_files = self.parse_upload_file(self.upload_file)
            raw_filepaths.extend(upload_files)

        # Process the raw filepaths (to account for directories, image sequences, formatting, etc)
        return file_utils.process_upload_filepaths(raw_filepaths)


    def parse_upload_file(self, upload_filepath):
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


def run_submit(args):
    # convert the Namespace object to a dictionary
    args_dict = vars(args)
    logger.debug('parsed_args is %s', args_dict)
    submitter = Submit(args_dict)
    response, response_code = submitter.main()
    logger.debug("Response Code: %s", response_code)
    logger.debug("Response: %s", response)
    if response_code in [201, 204]:
        logger.info("Submission Complete")
    else:
        logger.error("Submission Failure. Response code: %s", response_code)
        sys.exit(1)
