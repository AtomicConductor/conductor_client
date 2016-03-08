#!/usr/bin/env python

""" Command Line General Submitter for sending jobs and uploads to Conductor

"""
import getpass
import imp
import json
import logging
import os
import re
import sys
import time

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from conductor import CONFIG
from conductor.lib import file_utils, api_client, uploader, loggeria

logger = logging.getLogger(__name__)


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
        self.output_path = args.get('output_path')
        self.upload_file = args.get('upload_file')
        self.upload_only = args.get('upload_only')
        self.job_title = args.get('job_title') or ""
        self.enforced_md5s = args.get("enforced_md5s") or {}

        # Apply client config values in cases where arguments have not been passed in
        self.cores = args.get('cores', CONFIG["instance_cores"])
        self.machine_flavor = args.get('machine_type') or CONFIG["instance_flavor"]

        self.resource = args.get('resource', CONFIG["resource"])
        self.priority = args.get('priority', CONFIG["priority"])

        # Get any upload files/dirs listed in the config.yml
        self.upload_paths = CONFIG.get('upload_paths') or []
        assert isinstance(self.upload_paths, list), "Not a list: %s" % self.upload_paths
        # Append any upload files/dirs specified via the command line
        self.upload_paths.extend(args.get('upload_paths') or [])
        logger.debug("Upload_paths: %s", self.upload_paths)

        #  Get any environment variable settings from config.yml
        self.environment = CONFIG.get("environment") or {}
        assert isinstance(self.environment, dict), "Not a dictionary: %s" % self.environment
        # Then override any that were specified in the command line
        self.environment.update(args.get('env', {}))
        logger.debug("environment: %s", self.environment)

        self.local_upload = self.resolve_arg("local_upload", args, CONFIG)
        logger.debug("local_upload: %s", self.local_upload)

        self.md5_caching = self.resolve_arg("md5_caching", args, CONFIG)
        logger.debug("md5_caching: %s", self.md5_caching)

        self.database_filepath = self.resolve_arg("database_filepath", args, CONFIG)
        logger.debug("database_filepath: %s", self.database_filepath)

        self.location = args.get('location') or CONFIG.get("location")
        self.docker_image = args.get('docker_image') or CONFIG.get("docker_image")

        self.notify = { "emails": [],
                        "slack": []}
        if args.get('notify'):
            self.notify["emails"].extend(args.get('notify'))
        if CONFIG.get('notify'):
            if len(CONFIG.get('notify').split()) == 1:
                self.notify["emails"].append(CONFIG.get('notify'))
            else:
                self.notify["emails"].extend(CONFIG.get('notify').split())
        if args.get('slack_notify'):
            self.notify["slack"].extend(args.get('slack_notify'))
        if CONFIG.get('slack_notify'):
            if len(CONFIG.get('notify').split()) == 1:
                self.notify["slack"].append(CONFIG.get('slack_notify'))
            else:
                self.notify["slack"].extend(CONFIG.get('slack_notify'))

        logger.debug("Consumed args")

    @classmethod
    def resolve_arg(cls, arg_name, args, config):
        '''
        Helper function to resolve the value of an argument.
        The order of resolution is:
        1. Check whether the user explicitly specified the argument when calling/
           instantiating the class. If so, then use it, otherwise...
        2. Attempt to read it from the config.yml. If it's there, then use it, otherwise...
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


    def validate_args(self):
        '''
        Ensure that the combination of arguments don't result in an invalid job/request
        '''
        # TODO: Clean this shit up
        if self.raw_command and self.frames:
            pass

        elif self.upload_only and (self.upload_file or self.upload_paths):
            pass

        else:
            raise BadArgumentError('The supplied arguments could not submit a valid request.')

        if self.machine_flavor not in ["standard", "highmem", "highcpu"]:
            raise BadArgumentError("Machine type %s is not \"highmem\", \"standard\", or \"highcpu\"" % self.machine_flavor)

        if self.machine_flavor in ["highmem", "highcpu"] and self.cores < 2:
            raise BadArgumentError("highmem and highcpu machines have a minimum of 2 cores")


    def send_job(self, upload_files):
        '''
        Construct args for two different cases:
            - upload_only
            - running an actual command (cmd)


        upload_files: dict, where they key is the filepath, and the value is the md5. e.g.
                    {"/batman/v06/batman_v006_high.abc": "oFUgxKUUOFIHJ9HEvaRwgg==",
                    "/batman/v06/batman_v006_high.png": "s9y36AyAR5cYoMg0Vx1tzw=="}

        '''
        assert isinstance(upload_files, dict), "Expected dictionary. Got: %s" % upload_files

        logger.debug("upload_files:\n\t%s", "\n\t".join(upload_files or {}))

        submit_dict = {'owner':self.user}
        submit_dict['location'] = self.location
        submit_dict['docker_image'] = self.docker_image
        submit_dict['local_upload'] = self.local_upload
        submit_dict['job_title'] = self.job_title
        submit_dict['notify'] = self.notify

        if upload_files:
            submit_dict['upload_files'] = upload_files

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
                                'cores':self.cores,
                                'machine_flavor':self.machine_flavor})

            if self.priority:
                submit_dict['priority'] = self.priority
            if self.output_path:
                submit_dict['output_path'] = self.output_path
            if self.environment:
                submit_dict['environment'] = self.environment


        logger.debug("send_job JOB ARGS:")
        for arg_name, arg_value in sorted(submit_dict.iteritems()):
            logger.debug("\t%s: %s", arg_name, arg_value)

        logger.info("Sending Job...")
        response, response_code = self.api_client.make_request(uri_path="jobs/", data=json.dumps(submit_dict))
        if response_code not in [201, 204]:
            raise Exception("Job Submission failed: Error %s ...\n%s" % (response_code, response))
        return response, response_code


    def main(self):
        '''
        Submitting a job happens in a few stages:
            1. Gather depedencies and parameters for the job
            2. Upload dependencies to cloud storage (requires md5s of dependencies)
            3. Submit job to conductor (listing the dependencies and their corresponding md5s)
            
        In order to give flexibility to customers (because a customer may consist
        of a single user or a large team of users), there are two options avaiable
        that can dicate how these job submission stages are executed.
        In a simple single-user case, a user's machine can doe all three
        of the job submission stages.  Simple.  We call this local_upload=True.
        
        However, when there are multiple users, there may be a desire to funnel
        the "heavier" job submission duties (such as md5 checking and dependency 
        uploading) onto one dedicated machine (so as not to bog down
        the artist's machine). This is called local_upload=False. This results 
        in stage 1 being performed on the artist's machine (dependency gathering), while 
        handing over stage 2 and 3 to an uploader daemon.  This is achieved by
        the artist submitting a "partial" job, which only lists the dependencies
        that it requires (omitting the md5 hashes). In turn, the uploader daemon
        listens for these partial jobs, and acts upon them, by reading each job's
        listed dependencies (the filepaths that were recorded during the "partial" 
        job submission).  The uploader then  md5 checks each dependency file from it's local
        disk, then uploads the file to cloud storage (if necesseary), and finally "completes"
        the partial job submission by providing the full mapping dictionary of
        each dependency filepath and it's corresponing md5 hash. Once the job
        submission is completed, conductor can start acting on the job (executing
        tasks, etc).
        
        '''

        # Get the list of file dependencies
        upload_files = self.get_upload_files()

        # Create a dictionary of upload_files with None as the values.
        upload_files = dict([(path, None) for path in upload_files])

        # If opting to upload locally (i.e. from this machine) then run the uploader now
        # This will do all of the md5 hashing and uploading files to the conductor (if necesary).
        if self.local_upload:
            uploader_args = {"location":self.location,
                             "database_filepath":self.database_filepath,
                             "md5_caching": self.md5_caching}
            uploader_ = uploader.Uploader(uploader_args)
            upload_error_message = uploader_.handle_upload_response(upload_files)
            if upload_error_message:
                raise Exception("Could not upload files:\n%s" % upload_error_message)
            # Get the resulting dictionary of the file's and their corresponding md5 hashes
            upload_files = uploader_.return_md5s()

        # If the NOT uploading locally (i.e. offloading the work to the uploader daemon
        else:
            # update the upload_files dictionary with md5s that should be enforced
            # this will override the None values with actual md5 hashes
            for filepath, md5 in self.enforced_md5s.iteritems():
                processed_filepaths = file_utils.process_upload_filepath(filepath)
                assert len(processed_filepaths) == 1, "Did not get exactly one filepath: %s" % processed_filepaths
                upload_files[processed_filepaths[0]] = md5

        # Submit the job to conductor. upload_files may have md5s included in dictionary or may not.
        # Any md5s that are incuded, are expected to be checked against if/when the uploader
        # daemon goes to upload them. If they do not match what is on disk, the uploader will fail the job
        response, response_code = self.send_job(upload_files)
        return json.loads(response), response_code

    def get_upload_files(self):
        '''
        Resolve the "upload_paths" and "upload_file" arguments to return a single list
        of paths.
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
            return [line.strip() for line in file_.readlines]


class BadArgumentError(ValueError):
    pass


def run_submit(args):
    # convert the Namespace object to a dictionary
    args_dict = vars(args)

    # Set up logging
    log_level_name = args_dict.get("log_level") or CONFIG.get("log_level")
    log_level = loggeria.LEVEL_MAP.get(log_level_name)
    log_dirpath = args_dict.get("log_dir") or CONFIG.get("log_dir")
    set_logging(log_level, log_dirpath)

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


def set_logging(level=None, log_dirpath=None):
    log_filepath = None
    if log_dirpath:
        log_filepath = os.path.join(log_dirpath, "conductor_submit_log")
    loggeria.setup_conductor_logging(logger_level=level,
                                     console_formatter=loggeria.FORMATTER_VERBOSE,
                                     file_formatter=loggeria.FORMATTER_VERBOSE,
                                     log_filepath=log_filepath)

