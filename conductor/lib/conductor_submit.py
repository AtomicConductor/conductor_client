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
import types

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
    metadata_types = types.StringTypes


    def __init__(self, args):
        logger.debug("Init Submit")
        self.timeid = int(time.time())
        self.consume_args(args)
        self.validate_args()
        self.api_client = api_client.ApiClient()


    def consume_args(self, args):
        '''
        "Consume" the give arguments (which have been parsed by argparse).
        For arguments that have not been specified by the user via the command
        line, default to reasonable values.  
        If inherit_config is True, then default unspecified arguments to those
        values found in the config.yml file.
        
        1. Use the argument provided by the user via the command line.  Note that
           this may be a non-True value, such as False or 0.  So the only way
           to know whether the argument was provided by the user is to check
           whether is value is not None (which implies that argparse arguments
           should not be configured to give a default value when the user has
           not specified them).
           
       2. If the user has not provided the argument, and if inherit_config is
          True, then use the value found in the config.  
          
       3. If inherit_config is False or the the value in the config doesn't 
          exist, then default to an empty or non-True value.
        
        '''

        self.command = self.resolve_arg(args, 'cmd', "")
        logger.debug("command: %s", self.command)

        self.cores = self.resolve_arg(args, 'cores', 8)
        logger.debug("cores: %s", self.cores)

        self.database_filepath = self.resolve_arg(args, 'database_filepath', "")
        logger.debug("database_filepath: %s", self.database_filepath)

        self.docker_image = self.resolve_arg(args, 'docker_image', "")
        logger.debug("docker_image: %s", self.docker_image)

        self.enforced_md5s = self.resolve_arg(args, 'enforced_md5s', {})
        logger.debug("enforced_md5s: %s", self.enforced_md5s)

        self.environment = self.resolve_arg(args, 'environment', {}, combine_config=True)
        logger.debug("environment: %s", self.environment)

        self.frames = self.resolve_arg(args, 'frames', "")
        logger.debug("frames: %s", self.frames)

        self.job_title = self.resolve_arg(args, 'job_title', "")
        logger.debug("job_title: %s", self.job_title)

        self.local_upload = self.resolve_arg(args, 'local_upload', True)
        logger.debug("local_upload: %s", self.local_upload)

        self.location = self.resolve_arg(args, 'location', "")
        logger.debug("location: %s", self.location)

        self.machine_flavor = self.resolve_arg(args, 'machine_type', "standard")
        logger.debug("machine_flavor: %s", self.machine_flavor)

        metadata = self.resolve_arg(args, 'metadata', {}, combine_config=True)
        self.metadata = self.cast_metadata(metadata, strict=False)
        logger.debug("metadata: %s", self.metadata)

        self.md5_caching = self.resolve_arg(args, 'md5_caching', True)
        logger.debug("md5_caching: %s", self.md5_caching)

        self.output_path = self.resolve_arg(args, 'output_path', "")
        logger.debug("output_path: %s", self.output_path)

        self.priority = self.resolve_arg(args, 'priority', 5)
        logger.debug("priority: %s", self.priority)

        self.resource = self.resolve_arg(args, 'resource', "")
        logger.debug("resource: %s", self.resource)

        self.upload_file = self.resolve_arg(args, 'upload_file', "")
        logger.debug("upload_file: %s", self.upload_file)

        self.upload_only = self.resolve_arg(args, 'upload_only', False)
        logger.debug("upload_only: %s", self.upload_only)

        self.upload_paths = self.resolve_arg(args, 'upload_paths', [], combine_config=True)
        logger.debug("upload_paths: %s", self.upload_paths)

        self.user = self.resolve_arg(args, 'user', getpass.getuser())
        logger.debug("user: %s", self.user)

        self.notify = { "emails": self.resolve_arg(args, 'notify', [], combine_config=True),
                        "slack": self.resolve_arg(args, 'slack_notify', [], combine_config=True)}
        logger.debug("notify: %s", self.notify)

        logger.debug("Consumed args")

    @classmethod
    def resolve_arg(cls, args, arg_name, default, combine_config=False):
        '''
        Helper function to resolve the value of an argument.  The general premise
        is as follows:
        If an argument value was provided then use it.  However, if the combine_config,
        bool is True, then we want to combine that value with the value found in
        the config.  This only works with argument types which can be combined,
        such as lists or dictionaries. In terms of which value trumps the other,
        the argument value will always trump the config value. For example,
        if the config declared a dictionary value, and the argument also provided
        a dictionary value, they would both be combined, however, the argument
        value will replace any keys that clash with keys from the config value.
        
        If the argument nor the config have a value, then use the provided default value
        
        
        combine_config: bool. Indicates whether to combine the argument value
                        with the config value. This will only ever occur if
                        both values are present. 
        
        
        
        The order of resolution is:
        1. Check whether the user explicitly specified the argument when calling/
           instantiating the class.  This is indicated by whether the argument's 
           value is set to None or not. If the value is not None, then use it (
           combining it with the config value if appropriate)
           
        2. If the specified argument does not have value (i.e. it's None), then
           use the value found in the config. 
        
        3. If the config does not define the expected argument then use the default
           argument

        '''

        # Map a combine operation by type
        combine_op = {dict: dict.update,
                      list: list.extend}

        # Attempt to read the value from the args
        arg_value = args.get(arg_name)

        # This admittedly gets super convoluted..but not sure if it can be written any clearer...

        # If the config contains the argument name...
        if arg_name in CONFIG:
            config_value = CONFIG[arg_name]

            # If the arg value is  None, it indicates that the arg was not
            # explicity set. And if the config lists a value,then use it.
            # Note that it's valid that the config may state a non-True value (i.e. 0, False, etc)
            if arg_value == None:
                return config_value

            # IF we're here, then it means that the arg_Value is not None, so
            # simple check whehter we're combining its value with the the config
            # value.  If not, simply return the arg_value
            if not combine_config:
                return arg_value

            # If we're here, then it means that the arg_value is not None, and that
            # we're combining that value with the value found in the config.
            # Get the combine operation (update if dict, or extend if list)
            combine_op_ = combine_op.get(type(arg_value))
            # Ensure that the two values to be combined are or the proper type
            assert combine_op_, "Cannot combine data types of %s" % type(arg_value)
            assert type(config_value) == type(arg_value), "Cannot combine differing data types: %s, %s" % (config_value, arg_value)

            # because we're updating a list or dict from the config object, it will mutate. Make a copy first
            config_value = type(config_value)(config_value)
            # Call the Update or extend
            combine_op_(config_value, arg_value)
            return config_value

        # If the the config doesn't have a value
        else:
            # if the argument value is not None the simply return it
            if arg_value != None:
                return arg_value

            # if the arg_value is None then return the default argument
            return default



    def validate_args(self):
        '''
        Ensure that the combination of arguments don't result in an invalid job/request
        '''
        # TODO: Clean this shit up
        if self.command and self.frames:
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
        submit_dict['metadata'] = self.metadata

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
                                'command':self.command,
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
        response, response_code = self.api_client.make_request(uri_path="jobs/",
                                                               data=json.dumps(submit_dict),
                                                               raise_on_error=False)
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

    @classmethod
    def cast_metadata(cls, metadata, strict=False):
        '''
        Ensure that the data types in the given metadata are of the proper type
        (str or unicode). If strict is False, automatically cast (and warn)
        any values which do not conform.  If strict is True, do not cast values,
        simply raise an exception.  
        '''

        # Create a new metadata dictionary to return
        casted_metadata = {}

        # reusable error/warning message
        error_msg = 'Metadata %%s %%s is not of a supported type. Got %%s. Expected %s' % " or ".join([type_.__name__ for type_ in cls.metadata_types])

        for key, value in metadata.iteritems():

            key_type = type(key)
            if key_type not in cls.metadata_types:
                msg = error_msg % ("key", key, key_type)
                if strict:
                    raise Exception(msg)
                logger.warning(msg + ".  Auto casting value...")
                key = cls.cast_metadata_value(key)

            value_type = type(value)
            if value_type not in cls.metadata_types:
                msg = error_msg % ("value", value, value_type)
                if strict:
                    raise Exception(msg)
                logger.warning(msg + ".  Auto casting value...")
                value = cls.cast_metadata_value(value)

            # This should never happen, but need to make sure that the casting
            # process doesn't cause the original keys to collide with one another
            if key in casted_metadata:
                raise Exception("Metadata key collision due to casting: %s", key)
            casted_metadata[key] = value

        return casted_metadata


    @classmethod
    def cast_metadata_value(cls, value):
        '''
        Attempt to cast the given value to a unicode string
        '''

        # All the types that are supported for casting to metadata type
        cast_types = (bool, int, long, float, str, unicode)


        value_type = type(value)

        cast_error = "Cannot cast metadata value %s (%s) to unicode" % (value, value_type)

        # If the value's type is not one that can be casted, then raise an exception
        if value_type not in cast_types:
            raise Exception(cast_error)

        # Otherwise, attempt to cast the value to unicode
        try:
            return unicode(value)
        except:
            cast_error = "Casting failure. " + cast_error
            logger.error(cast_error)
            raise




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

