#!/usr/bin/env python

""" Command Line General Submitter for sending jobs and uploads to Conductor

"""
import argparse
from collections import namedtuple
import getpass
import imp
import json
import logging
import multiprocessing
import os
import Queue
import re
import sys
import threading
import time
import types
import traceback

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from conductor import CONFIG
from conductor.lib import common, file_utils, api_client, loggeria
from conductor.lib.common import sstr
from conductor.lib.uploader import Uploader

logger = logging.getLogger(__name__)

METADATA_TYPES = types.StringTypes

STATUS_UNINITIALIZED = "uninitialized"



'''


CRUD Operators


--- CLASSES ---
# Classes serve as a convenience "wrapper" that creates and augments entities to
# which ultimately represent common objects, such as submitting a "render job",
# or an "upload job"


 -- Submission --
   # Abstract baseclass

    --- ComputeSubmission ---
    # A class which creates a "regular render job". This does computation Upload
        -MetaData
        -Tasks
        -CostLimits?
        -
    
        SubmitComputeDaemon
        SubmitComputeLocal
        
    SubmitUpload
            SubmitUploadDaemon
            SubmitUploadLocal
        






'''



class Args(object):

    ARGS = {
            "database_filepath": {"type": str},
            "job_title":         {"type": str},
            "local_upload":      {"type": bool, "default": True},
            "location":          {"type": str},
            "log_dir":           {"type": str},
            "log_level":         {"type": str, "default": "INFO"},
            "md5_caching":       {"type": int, "default": True},
            "metadata":          {"type": dict},
            "notify":            {"type": dict},
            "priority":          {"type": int, "default": 5},
            "project":           {"type": (str, unicode)},
            "thread_count":      {"type": int, "default": multiprocessing.cpu_count() * 2},
            "owner":             {"type": str},
            "upload":            {"type": (str, unicode)},
            "upload_files":      {"type": dict},
             }

    
    @classmethod
    def process_args(cls, args, inherit_config=True):
        
        inherited_args = inherit_args()
        process_inherrited_args()
        args update
        
        cast_args(args)
        
    
    def get_inherited_args(cls, self):
        return cls.process_inherited_args()
        
    def get_



class ComputeArgs(Args):
    ARGS = dict(Args.ARGS)

    ARGS.update({"command":           {"type": str},
                 "chunk_size":        {"type": int, "default": 1},
                 "database_filepath": {"type": str},
                 "docker_image":      {"type": str},
                 "environment":       {"type": dict, "required"},
                 "instance_type":     {"type": str, "default": "n1-standard-8"},
                 "frame_padding":     {"type": int},
                 "frame_range":       {"type": str},
                 "max_instances":     {"type": int},
                 "output_path":       {"type": str},
                 "scout_frames":      {"type": str},
                 "software_packages": {"type": (list, tuple)}})
                 

    @classmethod
    def consume_args(cls, args):
        '''
        "Consume" the provided keyword arguments. For arguments that have not been 
        provided, or arguments with None value, default to reasonable values. 
        '''
        args = {}

        for arg_name, arg_data in cls.ARGS.iteritems():
            arg_value = resolve_arg(args, arg_name, arg_data.get("default"), read_config=read_config, combine_config=False)
            if arg_value != None and not isinstance(arg_value, arg_data["type"]):
                raise BadArgumentError("%r argument must be %s. Got: %s" % (arg_name, arg_data["type"], arg_value))
            args[arg_name] = arg_value
        return args



class UploadArgs(Args):
    ARGS = dict(Args.ARGS)

    ARGS.update({"command":           {"type": str},
                "chunk_size":        {"type": int, "default": 1},
                "database_filepath": {"type": str},
                "docker_image":      {"type": str},
                "environment":       {"type": dict},
                "instance_type":     {"type": str, "default": "n1-standard-8"},
                "frame_padding":     {"type": int},
                "frame_range":       {"type": str},
                "max_instances":     {"type": int},
                "output_path":       {"type": str},
                "scout_frames":      {"type": str},
                "software_packages": {"type": (list, tuple)}})




class Submission(object):
    '''
    A convenience class that automates the "building" of a "job"
    This entails several steps and entity creation.
    
        Job
        Upload
        MetaData
    
    
    kwargs should be 
    
    '''
    ARGS = {
            "database_filepath": {"type": str},
            "job_title":         {"type": str},
            "local_upload":      {"type": bool, "default": True},
            "location":          {"type": str},
            "log_dir":           {"type": str},
            "log_level":         {"type": str, "default": "INFO"},
            "md5_caching":       {"type": int, "default": True},
            "metadata":          {"type": dict},
            "notify":            {"type": dict},
            "priority":          {"type": int, "default": 5},
            "project":           {"type": (str, unicode)},
            "thread_count":      {"type": int, "default": multiprocessing.cpu_count() * 2},
            "owner":             {"type": str},
            "upload":            {"type": (str, unicode)},
            "upload_files":      {"type": dict},
             }


    def __init__(self, args):
        args = self.process_args(**args)
        self.validate_args(**kwargs)
        self.args = argparse.Namespace(**kwargs)
        from pprint import pprint
        pprint(self.args.__dict__)

    def process_args(self, **kwargs):
        metadata = kwargs.get("metadata")
        if metadata:
            kwargs["metadata"] = cast_metadata(metadata)
        return kwargs

    def validate_args(self, **kwargs):
        assert kwargs["project"]
        assert kwargs["owner"]
        
        # validate that both are not simultaneously provided
        assert not (kwargs["upload"] and kwargs["upload_files"])

    @classmethod
    def consume_args(cls, read_config, **kwargs):
        '''
        "Consume" the provided keyword arguments. For arguments that have not been 
        provided, or arguments with None value, default to reasonable values. 
        '''
        args = {}

        for arg_name, arg_data in cls.ARGS.iteritems():
            arg_value = resolve_arg(kwargs, arg_name, arg_data.get("default"), read_config=read_config, combine_config=False)
            if arg_value != None and not isinstance(arg_value, arg_data["type"]):
                raise BadArgumentError("%r argument must be %s. Got: %s" % (arg_name, arg_data["type"], arg_value))
            args[arg_name] = arg_value
        return args

    @classmethod
    @common.dec_function_timer
    def submit(cls, args, inherit_config=True):
        '''
        - Create entities
        - Set entity state
        '''
        args = cls.consume_args(inherit_config, **kwargs)
        submission = cls(**args)
        resources = submission.create_resources()
        metadata = resources
        job = resources.get("job")
        upload = resources.get("upload")
        submission.initialize(job, upload)


        if submission.args.local_upload and upload:
            submission.run_uploader(upload)



    @common.dec_function_timer
    def create_resources(self):
        resources = {}

        #------------------------
        # METADATA
        #------------------------
        if self.args.metadata:
            logger.info("Creating metadata...")
            metadata = self.post_metadata(**self.args.metadata)
            logger.debug("metadata: %s", metadata)
            self.args.metadata = metadata['id']
            resources["metadata"] = metadata


        #-----------------------
        # UPLOAD
        #-----------------------
        if self.args.upload_files:
            # If there are upload files provided, then create an Upload resource
            
            # Get the total bytes of all files that are part of the job
            logger.info("Calculating upload files size...")
            total_size = sum([os.stat(f).st_size for f in  self.args.upload_files.keys()])


            upload = self.post_upload(location=self.args.location,
                                      metadata=self.args.metadata,
                                      owner=self.args.owner,
                                      project=self.args.project,
                                      status=STATUS_UNINITIALIZED,
                                      total_size=total_size,
                                      upload_files=self.args.upload_files)

            logger.debug("upload: %s", upload)
            self.args.upload = upload["id"]
            resources["upload"] = upload


        #-----------------------
        # JOB
        #-----------------------
        job = self.post_job(
                            chunk_size=self.args.chunk_size,
                            command=self.args.command,
                            docker_image=self.args.docker_image,
                            environment=self.args.environment,
                            frame_padding=self.args.frame_padding,
                            frame_range=self.args.frame_range,
                            instance_type=self.args.instance_type,
                            job_title=self.args.job_title,
                            location=self.args.location,
                            max_instances=self.args.max_instances,
                            metadata=self.args.metadata,
                            notify=self.args.notify,
                            owner=self.args.owner,
                            output_path=self.args.output_path,
                            priority=self.args.priority,
                            project=self.args.project,
                            scout_frames=self.args.scout_frames,
                            software_packages=self.args.software_packages,
                            upload=self.args.upload)



        logger.debug("job: %s", job)
        resources["job"] = job
        return resources





#     @common.dec_function_timer
#     def consummate(self, job, upload=None):
#
#         '''
#         start/complete/seal/conclude/consummate
#         Set Statuses for:
#             Job
#             Task
#             Upload
#         '''
#
#         if upload:
#             if self.args.local_upload:
#                 upload_status = "client_in_progress"
#                 job_status = "uploading"
#             else:
#                 upload_status = "client_pending"
#                 job_status = "upload_pending"
#         else:
#             logger.warning("No upload created for job")
#             job_status = "pending"
#
#
#
#
#         logger.info("Setting Tasks status..")
#         task_info = Queue.Queue()
#         [task_info.put((task_id, {"status":job_status})) for task_id in job.get("task_keys") or []]
#         task_updater = UpdateTasks(task_info)
#         task_updater.run()
#         print task_updater._error_queue
#         print task_updater._work_queue
#         print task_updater._output_queue
#
#         logger.info("Setting Job status..")
#         self._put_job(job["id"], status=job_status)
#
#         if upload:
#             self._put_upload(upload["id"], {"status": upload_status})

    @common.dec_function_timer
    def initialize(self, job_ids, :

        '''
        start/complete/seal/conclude/consummate
        Set Statuses for:
            Job
            Task
            Upload
        '''
        

        if upload:
            if self.args.local_upload:
                job_status = "uploading"
            else:
                job_status = "upload_pending"
        else:
            logger.warning("No upload created for job")
            job_status = "pending"

        return self.initialize_jobs(job_ids, job_status)


    @classmethod
    @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def initialize_jobs(cls, job_ids, job_status):
        logger.debug("job_ids: %s", job_ids)
        logger.debug("job_status: %s", job_status)

        json_data = {"job_status":job_status,
                     "ids": job_ids}

        endpoint = "jobs/initialize/"
        response = api_client.AppRequest.app_request(http_method="POST",
                                                      endpoint=endpoint,
                                                      json_data=json_data,
                                                      raise_error=True)
        if response.status_code not in [200]:
            msg = "Failed to Initialize job(s) via" % endpoint
            msg += "\nError %s %s\n%s" % (response.status_code, response.reason, response.content)
            raise Exception(msg)
        return response.json()


    @classmethod
    @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def post_upload(cls, **attributes):
        cls.validate_upload_attributes(**attributes)
        return api_client.post_upload(**attributes)


    @classmethod
    def validate_upload_attributes(cls, owner, project, status, upload_files, total_size, metadata=None, location=None):
        '''
        upload_files*: dict
        status*: str. 
        project*: str. id of the project entity
        total_size* = int. total byes of all files in the upload
        '''

        required_args = [owner,
                         upload_files,
                         status,
                         project,
                         total_size]

        for arg in required_args:
            if arg == None:
                raise Exception("Upload is missing required %r argument" % arg)




    @classmethod
    @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def post_metadata(cls, **attributes):
        cls.validate_metadata_attributes(**attributes)
        return api_client.post_metadata(**attributes)




    @classmethod
    def validate_metadata_attributes(cls, **attrubutes):
        '''
        upload_files*: dict
        status*: str. 
        project*: str. id of the project entity
        total_size* = int. total byes of all files in the upload
        '''



    @classmethod
    @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def post_job(cls, **attributes):
        '''
        
        project_id
        owner
    
        kwargs: optional job arguments:
            chunk_size
            command
            cores
            docker_image
            environment
            frame_range
            instance_type #TODO!! 
            job_title
            local_upload
            location
            machine_flavor
            max_instances
            metadata
            notify, 
            output_path
            priority
            software_package_ids
            scout_frames
            upload_id
        '''

        logger.debug("#### JOB ARGS ####:")
        for arg_name, arg_value in sorted(attributes.iteritems()):
            logger.debug("\t%s: %s", arg_name, arg_value)
        endpoint = "/jobs/"
        response = api_client.AppRequest.app_request(http_method="POST",
                                                  endpoint=endpoint,
                                                  params=None,
                                                  json_data=attributes,
                                                  raise_error=True)
        if response.status_code not in [201]:
            msg = "Failed to POST Job to Conductor"
            msg += "\nError %s %s\n%s" % (response.status_code, response.reason, response.content)
            raise Exception(msg)

        json_data = response.json()
        resource_data = json_data.get("data")
        if resource_data == None:
            raise Exception('Json response does not have expected key: "data"\nJson data: \n%s' % json_data)

        return resource_data


    @classmethod
    @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def _get_job(cls, job_id, params=None):
        return api_client.get_job(job_id, params=params)

    @classmethod
    @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def _post_job(cls, attributes):
        return api_client.post_job(**attributes)

    @classmethod
    @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def _put_job(cls, job_id, **attributes):
        return api_client.put_job(job_id, **attributes)

    @classmethod
    @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def _get_task(cls, task_id, params=None):
        return api_client.get_task(task_id, params=params)

    @classmethod
    @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def _post_task(cls, attributes):
        return api_client.post_task(**attributes)

    @classmethod
    @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def _put_task(cls, task_id, **attributes):
        return api_client.put_task(task_id, **attributes)

    @classmethod
    @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def _get_upload(cls, upload_id, params=None):
        return api_client.get_upload(upload_id, params=params)

    @classmethod
    @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def _put_upload(cls, upload_id, attributes):
        return api_client.put_upload(upload_id, **attributes)


    def run_uploader(self, upload):
        uploader_ = Uploader(location=self.args.location,
                             thread_count=self.args.thread_count,
                             database_filepath=self.args.database_filepath,
                             md5_caching=self.args.md5_caching)



        uploader_.upload_one(upload)
        # Get the resulting dictionary of the file's and their corresponding md5 hashes
        return uploader_.return_md5s()


class ComputeSubmission(Submission):

    ARGS = dict(Submission.ARGS)

    ARGS.update({"command":           {"type": str},
                "chunk_size":        {"type": int, "default": 1},
                "database_filepath": {"type": str},
                "docker_image":      {"type": str},
                "environment":       {"type": dict},
                "instance_type":     {"type": str, "default": "n1-standard-8"},
                "frame_padding":     {"type": int},
                "frame_range":       {"type": str},
                "max_instances":     {"type": int},
                "output_path":       {"type": str},
                "scout_frames":      {"type": str},
                "software_packages": {"type": (list, tuple)}})


    def validate_args(self, **kwargs):
        super(ComputeSubmission, self).validate_args(**kwargs)
        assert kwargs.get("command")
        assert kwargs.get("instance_type")
        assert kwargs.get("frame_range")
        assert kwargs.get("output_path")
        assert kwargs.get("software_packages")


    def get_job_args(self):
        job_args = super(ComputeSubmission, self).get_job_args()
        # Arguments relevant to Render Jobs
        job_args.update({"chunk_size":self.args.chunk_size,
                        "command":self.args.command,
                        "docker_image": self.args.docker_image,
                        "environment": self.args.environment,
                        "frame_range": self.args.frame_range,
                        "job_title": self.args.job_title,
                        "instance_type": self.args.instance_type,
                        "max_instances":self.args.max_instances,
                        "output_path": self.args.output_path,
                        "priority":str(self.args.priority).zfill(3),  # TODO:(lws) let's  use integers please
                        "scout_frames":self.args.scout_frames,
                        "software_packages":self.args.software_packages})
        return job_args


class UploadSubmission(Submission):

    def validate_args(self, **kwargs):
        pass

    def get_job_args(self):
        job_args = super(UploadSubmission, self).get_job_args()
        job_args.update({"job_title": "UPLOAD %s" % self.args.job_title})
        return job_args


#
#
# class Submit(object):
#     """ Conductor Submission
#     Command Line Usage:
#         $ python conductor_submit.py --upload_file /path/to/upload_file.txt --frames 1001-1100 --cmd
#
#     Help:
#         $ python conductor_submit.py -h
#     """
#
#     response = None
#     error = None
#
#     def __init__(self, args, raise_error=True):
#         self._args = self.consume_args(args)
#         self.validate_args()
#         try:
#             self.response = self.submit(raise_error=True)
#         except:
#             stack_trace = traceback.format_exc()
#             self.error = stack_trace
#             if raise_error:
#                 raise
#
#
#     def consume_args(self, args):
#         '''
#         "Consume" the give arguments (which have been parsed by argparse).
#         For arguments that have not been specified by the user via the command
#         line, default to reasonable values.
#         If inherit_config is True, then default unspecified arguments to those
#         values found in the config.yml file.
#
#         1. Use the argument provided by the user via the command line.  Note that
#            this may be a non-True value, such as False or 0.  So the only way
#            to know whether the argument was provided by the user is to check
#            whether is value is not None (which implies that argparse arguments
#            should not be configured to give a default value when the user has
#            not specified them).
#
#        2. If the user has not provided the argument, and if inherit_config is
#           True, then use the value found in the config.
#
#        3. If inherit_config is False or the the value in the config doesn't
#           exist, then default to an empty or non-True value.
#
#         '''
#
#         self.command = self.resolve_arg(args, 'cmd', "")
#         logger.debug("command: %s", self.command)
#
#         self.cores = self.resolve_arg(args, 'cores', 8)
#         logger.debug("cores: %s", self.cores)
#
#         self.database_filepath = self.resolve_arg(args, 'database_filepath', "")
#         logger.debug("database_filepath: %s", self.database_filepath)
#
#         self.docker_image = self.resolve_arg(args, 'docker_image', "")
#         logger.debug("docker_image: %s", self.docker_image)
#
#         self.enforced_md5s = self.resolve_arg(args, 'enforced_md5s', {})
#         logger.debug("enforced_md5s: %s", self.enforced_md5s)
#
#         self.environment = self.resolve_arg(args, 'environment', {}, combine_config=True)
#         logger.debug("environment: %s", sstr(self.environment))
#
#         self.frame_range = self.resolve_arg(args, 'frames', "")
#         logger.debug("frame_range: %s", self.frame_range)
#
#         self.job_title = self.resolve_arg(args, 'job_title', "")
#         logger.debug("job_title: %s", self.job_title)
#
#         self.local_upload = self.resolve_arg(args, 'local_upload', True)
#         logger.debug("local_upload: %s", self.local_upload)
#
#         self.location = self.resolve_arg(args, 'location', "")
#         logger.debug("location: %s", self.location)
#
#         self.machine_flavor = self.resolve_arg(args, 'machine_type', "standard")
#         logger.debug("machine_flavor: %s", self.machine_flavor)
#
#         metadata = self.resolve_arg(args, 'metadata', {}, combine_config=True)
#         self.metadata = self.cast_metadata(metadata, strict=False)
#         logger.debug("metadata: %s", sstr(self.metadata))
#
#         self.metadata_id = self.resolve_arg(args, 'metadata_id', "")
#         logger.debug("metadata_id: %s", self.metadata_id)
#
#         self.md5_caching = self.resolve_arg(args, 'md5_caching', True)
#         logger.debug("md5_caching: %s", self.md5_caching)
#
#         self.output_path = self.resolve_arg(args, 'output_path', "")
#         logger.debug("output_path: %s", self.output_path)
#
#         self.priority = self.resolve_arg(args, 'priority', 5)
#         logger.debug("priority: %s", self.priority)
#
#         self.project = self.resolve_arg(args, 'project', "")
#         logger.debug("project: %s", self.project)
#
#         self.scout_frames = self.resolve_arg(args, 'scout_frames', "")
#         logger.debug("scout_frames: %s", self.scout_frames)
#
#         self.software_package_ids = self.resolve_arg(args, 'software_package_ids', [], combine_config=True)
#         logger.debug("software_package_ids: %s", self.software_package_ids)
#
#         self.upload_file = self.resolve_arg(args, 'upload_file', "")
#         logger.debug("upload_file: %s", self.upload_file)
#
#         self.upload_only = self.resolve_arg(args, 'upload_only', False)
#         logger.debug("upload_only: %s", self.upload_only)
#
#         self.max_instances = self.resolve_arg(args, 'max_instances', 0)
#         logger.debug("max_instances: %s", self.max_instances)
#
#         self.chunk_size = self.resolve_arg(args, 'chunk_size', 1)
#         logger.debug("chunk_size: %s", self.chunk_size)
#
#         self.upload_id = self.resolve_arg(args, 'upload_id', "")
#         logger.debug("upload_id: %s", self.upload_id)
#
#         self.upload_paths = self.resolve_arg(args, 'upload_paths', [], combine_config=True)
#         logger.debug("upload_paths: %s", sstr(self.upload_paths))
#
#         self.owner = self.resolve_arg(args, 'user', getpass.getuser())
#         logger.debug("owner: %s", self.owner)
#
#         self.notify = { "emails": self.resolve_arg(args, 'notify', [], combine_config=True),
#                         "slack": self.resolve_arg(args, 'slack_notify', [], combine_config=True)}
#         logger.debug("notify: %s", self.notify)
#
#         self.thread_count = self.resolve_arg(args, "thread_count", 6)  # TODO:(lws): expose thread count in Submit command
#         logger.debug("thread_count: %s", self.thread_count)
#
#         self.instance_type = "n1-%s-%s" % (self.machine_flavor, self.cores)  # TODO:(lws)Get rid of the cores and machine flavor)
#         logger.debug("instance_type: %s", self.instance_type)
#
#     @classmethod
#     def resolve_arg(cls, args, arg_name, default, combine_config=False):
#         '''
#         Helper function to resolve the value of an argument.  The general premise
#         is as follows:
#         If an argument value was provided then use it.  However, if the combine_config,
#         bool is True, then we want to combine that value with the value found in
#         the config.  This only works with argument types which can be combined,
#         such as lists or dictionaries. In terms of which value trumps the other,
#         the argument value will always trump the config value. For example,
#         if the config declared a dictionary value, and the argument also provided
#         a dictionary value, they would both be combined, however, the argument
#         value will replace any keys that clash with keys from the config value.
#
#         If the argument nor the config have a value, then use the provided default value
#
#
#         combine_config: bool. Indicates whether to combine the argument value
#                         with the config value. This will only ever occur if
#                         both values are present.
#
#
#
#         The order of resolution is:
#         1. Check whether the user explicitly specified the argument when calling/
#            instantiating the class.  This is indicated by whether the argument's
#            value is set to None or not. If the value is not None, then use it (
#            combining it with the config value if appropriate)
#
#         2. If the specified argument does not have value (i.e. it's None), then
#            use the value found in the config.
#
#         3. If the config does not define the expected argument then use the default
#            argument
#
#         '''
#
#         # Map a combine operation by type
#         combine_op = {dict: dict.update,
#                       list: list.extend}
#
#         # Attempt to read the value from the args
#         arg_value = args.get(arg_name)
#
#         # This admittedly gets super convoluted..but not sure if it can be written any clearer...
#
#         # If the config contains the argument name...
#         if arg_name in CONFIG:
#             config_value = CONFIG[arg_name]
#
#             # If the arg value is  None, it indicates that the arg was not
#             # explicitly set. And if the config lists a value,then use it.
#             # Note that it's valid that the config may state a non-True value (i.e. 0, False, etc)
#             if arg_value == None:
#                 return config_value
#
#             # IF we're here, then it means that the arg_Value is not None, so
#             # simple check whether we're combining its value with the the config
#             # value.  If not, simply return the arg_value
#             if not combine_config:
#                 return arg_value
#
#             # If we're here, then it means that the arg_value is not None, and that
#             # we're combining that value with the value found in the config.
#             # Get the combine operation (update if dict, or extend if list)
#             combine_op_ = combine_op.get(type(arg_value))
#             # Ensure that the two values to be combined are or the proper type
#             assert combine_op_, "Cannot combine data types of %s" % type(arg_value)
#             assert type(config_value) == type(arg_value), "Cannot combine differing data types: %s, %s" % (config_value, arg_value)
#
#             # because we're updating a list or dict from the config object, it will mutate. Make a copy first
#             config_value = type(config_value)(config_value)
#             # Call the Update or extend
#             combine_op_(config_value, arg_value)
#             return config_value
#
#         # If the the config doesn't have a value
#         else:
#             # if the argument value is not None the simply return it
#             if arg_value != None:
#                 return arg_value
#
#             # if the arg_value is None then return the default argument
#             return default
#
#
#
#     def validate_args(self):
#         '''
#         Ensure that the combination of arguments don't result in an invalid job/request
#         '''
#         # TODO: Clean this shit up
#         if self.command and self.frame_range:
#             pass
#
#         elif self.upload_only and (self.upload_file or self.upload_paths):
#             pass
#
#         else:
#             raise BadArgumentError('The supplied arguments could not submit a valid request.')
#
#         if self.upload_id and self.upload_paths:
#             raise BadArgumentError('Job may not specify both an upload_id (%s)'
#                                    'as well as upload_paths (%s of them). Must choose one route',
#                                    self.upload_id, len(self.self.upload_paths))
#
#         if self.metadata_id and self.metadata:
#             raise BadArgumentError('Job may not specify both a metadata_id (%s)'
#                                    'as well as a metadata dict (%s). Must choose one route',
#                                    self.metadata_id, len(self.self.metadata))
#
#
#         if self.machine_flavor not in ["standard", "highmem", "highcpu"]:
#             raise BadArgumentError("Machine type %s is not \"highmem\", \"standard\", or \"highcpu\"" % self.machine_flavor)
#
#         if self.machine_flavor in ["highmem", "highcpu"] and self.cores < 2:
#             raise BadArgumentError("highmem and highcpu machines have a minimum of 2 cores")
#
#
#     def submit(self, raise_error=True):
#         '''
#         Submitting a job happens in a few stages:
#             1. Gather depedencies and parameters for the job
#             2. Upload dependencies to cloud storage (requires md5s of dependencies)
#             3. Submit job to conductor (listing the dependencies and their corresponding md5s)
#
#         In order to give flexibility to customers (because a customer may consist
#         of a single user or a large team of users), there are two options avaiable
#         that can dicate how these job submission stages are executed.
#         In a simple single-user case, a user's machine can doe all three
#         of the job submission stages.  Simple.  We call this local_upload=True.
#
#         However, when there are multiple users, there may be a desire to funnel
#         the "heavier" job submission duties (such as md5 checking and dependency
#         uploading) onto one dedicated machine (so as not to bog down
#         the artist's machine). This is called local_upload=False. This results
#         in stage 1 being performed on the artist's machine (dependency gathering), while
#         handing over stage 2 and 3 to an uploader daemon.  This is achieved by
#         the artist submitting a "partial" job, which only lists the dependencies
#         that it requires (omitting the md5 hashes). In turn, the uploader daemon
#         listens for these partial jobs, and acts upon them, by reading each job's
#         listed dependencies (the filepaths that were recorded during the "partial"
#         job submission).  The uploader then  md5 checks each dependency file from it's local
#         disk, then uploads the file to cloud storage (if necesseary), and finally "completes"
#         the partial job submission by providing the full mapping dictionary of
#         each dependency filepath and it's corresponing md5 hash. Once the job
#         submission is completed, conductor can start acting on the job (executing
#         tasks, etc).
#
#         '''
#
#         #------------------------
#         # PROJECT
#         #------------------------
#         project_id = self.get_project_id(self.project)
#
#
#         #------------------------
#         # METADATA
#         #------------------------
#         if self.metadata:
#             logger.info("Creating metadata...")
#             metadata = self.post_metadata(self.metadata)
#             metadata_id = metadata['id']
#         else:
#             metadata_id = self.metadata_id
#
#         logger.debug("metadata_id: %s", metadata_id)
#
#
#         #-----------------------
#         # UPLOAD
#         #-----------------------
#         # Get the list of file dependencies
#         logger.info("Reconciling upload files")
#         upload_filepaths = self.get_upload_files()
#
#         if upload_filepaths:
#             upload, future_upload_status = self.handle_upload(project_id, upload_filepaths, metadata_id=metadata_id)
#             logger.debug("upload: %s", upload)
#             upload_id = upload["id"]
#             future_job_status_map = {"server_pending":"sync_pending",
#                                      "client_pending":"upload_pending"}
#             future_job_status = future_job_status_map[future_upload_status]
#         else:
#             upload_id = None
#             future_upload_status = None
#             future_job_status = "pending"
#
#         logger.debug("upload_id: %s", upload_id)
#         logger.debug("future_upload_status: %s", future_upload_status)
#         logger.debug("future_job_status: %s", future_job_status)
#
#
#         #-----------------------
#         # JOB
#         #-----------------------
#
#         # arguments that are common across render and upload jobs
#         job_args = {"upload_only":self.upload_only,
#                     "location": self.location,
#                     "local_upload": self.local_upload,
#                     "metadata": metadata_id,
#                     "notify": self.notify,
#                     "project": project_id,
#                     "owner": self.owner,
#                     "upload":upload_id, }
#
#         # Arguments relevant to Render Jobs
#         render_job_args = {"chunk_size":self.chunk_size,
#                             "command":self.command,
#                             "docker_image": self.docker_image,
#                             "environment": self.environment,
#                             "frame_range": self.frame_range,
#                             "job_title": self.job_title,
#                             "instance_type": self.instance_type,  # TODO!!
#                             "max_instances":self.max_instances,
#                             "output_path": self.output_path,
#                             "priority":str(self.priority).zfill(3),  # TODO:(lws) let's  use integers please
#                             "scout_frames":self.scout_frames,
#                             "software_packages":self.software_package_ids}
#
#         # Arguments relevant to Upload jobs
#         upload_job_args = {"job_title": "UPLOAD %s" % self.job_title}
#
#
#         if self.upload_only:
#             job_args.update(upload_job_args)
#             print job_args
#             job = self.post_upload_job(**job_args)
#         else:
#             job_args.update(render_job_args)
#             print job_args
#             job = self.post_render_job(**job_args)
#
#
#         print job
#         self.initialize_job(job["id"], future_job_status, upload_id, future_upload_status)
#         logger.info("########## Job submitted ##########\n%s", sstr(job))
#
#
#
#     def handle_upload(self, project_id, upload_filepaths, metadata_id=None):
#
# #         {"/batman/v06/batman_v006_high.abc": "oFUgxKUUOFIHJ9HEvaRwgg==",
# #         "/batman/v06/batman_v006_high.png": "s9y36AyAR5cYoMg0Vx1tzw=="}
#
#         upload_args = {"location": self.location,
#                        "metadata": metadata_id,
#                        "owner": self.owner,
#                        "status": "uninitialized",
#                        "project": project_id}
#
#
#         # Get the total bytes of all files that are part of the job
#         logger.info("Calculating upload files size...")
#         total_size = sum([os.stat(f).st_size for f in  upload_filepaths])
#         upload_args["total_size"] = total_size
#         logger.info("Upload files size: %s", common.get_human_bytes(total_size))
#
#         # Create a dictionary of filepaths and their md5s
#
#         upload_dict = dict([(path, None) for path in upload_filepaths])
#         upload_args["upload_files"] = upload_dict
#
#         if self.local_upload:
#
#             #### LOCAL UPLOAD MODE ####
#
#             # If opting to upload locally (i.e. from this machine) then run the uploader now
#             # This will do all of the md5 hashing and uploading files to the conductor (if necessary).
#             upload = self.post_upload(upload_args)
#             upload_dict = self.run_uploader(upload)
#             finish_status = "server_pending"
#
#         #### DAEMON MODE ####
#         else:
#             # If the NOT uploading locally (i.e. offloading the work to the uploader daemon
#             # update the upload_files dictionary with md5s that should be enforced
#             # this will override the None values with actual md5 hashes
#
#             for filepath, md5 in self.enforced_md5s.iteritems():
#                 processed_filepaths = file_utils.process_upload_filepath(filepath)
#                 assert len(processed_filepaths) == 1, "Did not get exactly one filepath: %s" % processed_filepaths
#                 upload_dict[processed_filepaths[0]] = md5
#
#             upload_args["upload_files"] = upload_dict
#             upload = self.post_upload(upload_args)
#             finish_status = "client_pending"
#
#
#
#         return upload, finish_status
#
#
#
#
#
#
#     def run_uploader(self, upload):
#         # Create a dictionary of upload_files with None as the values.
#
#         uploader_ = Uploader(location=self.location,
#                              thread_count=self.thread_count,
#                              database_filepath=self.database_filepath,
#                              md5_caching=self.md5_caching)
#
#
#
#         uploader_.upload_one(upload)
#         # Get the resulting dictionary of the file's and their corresponding md5 hashes
#         return uploader_.return_md5s()
#
#
#     @classmethod
#     def post_job(cls, **attributes):
#         '''
#
#         project_id
#         owner
#
#         kwargs: optional job arguments:
#             chunk_size
#             command
#             cores
#             docker_image
#             environment
#             frame_range
#             instance_type #TODO!!
#             job_title
#             local_upload
#             location
#             machine_flavor
#             max_instances
#             metadata
#             notify,
#             output_path
#             priority
#             software_package_ids
#             scout_frames
#             upload_id
#         '''
#
#         logger.debug("#### JOB ARGS ####:")
#         for arg_name, arg_value in sorted(attributes.iteritems()):
#             logger.debug("\t%s: %s", arg_name, arg_value)
#
#         return cls._post_job(attributes)
#
#
#
#
#
#     @classmethod
#     @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
#     def post_render_job(cls, chunk_size=None, command=None, docker_image=None,
#                         environment=None, frame_range=None, instance_type=None,
#                         job_title=None, local_upload=True, location=None,
#                         max_instances=None, metadata=None, notify=None,
#                         output_path=None, owner=None, priority=None, project=None,
#                         scout_frames=None, software_packages=None,
#                         status=None, upload_only=False, upload=None):
#         '''
#         Note that these keyword arguments are here (instead of **kwargs) as a
#         way of ensuring that the only arguments with the proper names make it
#         through.  Obviously it doesn't validate their values.  TODO:(lws)
#         '''
#
#         return cls.post_job(chunk_size=chunk_size,
#                             command=command,
#                             docker_image=docker_image,
#                             environment=environment,
#                             frame_range=frame_range,
#                             instance_type=instance_type,
#                             job_title=job_title,
#                             local_upload=local_upload,
#                             location=location,
#                             max_instances=max_instances,
#                             metadata=metadata,
#                             notify=notify,
#                             output_path=output_path,
#                             owner=owner,
#                             priority=priority,
#                             project=project,
#                             scout_frames=scout_frames,
#                             software_packages=software_packages,
#                             status=status,
#                             upload_only=upload_only,
#                             upload=upload)
#
#
#     @classmethod
#     @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
#     def post_upload_job(cls, job_title=None, local_upload=True, location=None, metadata=None, notify=None, owner=None, project=None, status=None, upload_only=False, upload=None):
#         '''
#         Note that these keyword arguments are here (instead of **kwargs) as a
#         way of ensuring that the only arguments with the proper names make it
#         through.  Obviously it doesn't validate their values.  TODO:(lws)
#         '''
#         return cls.post_job(job_title=job_title,
#                             local_upload=local_upload,
#                             location=location,
#                             metadata=metadata,
#                             notify=notify,
#                             owner=owner,
#                             project=project,
#                             status=status,
#                             upload_only=upload_only,
#                             upload=upload)
#
#
#
#     @classmethod
#     def get_project_id(cls, project):
#         return  "%s|%s" % (CONFIG["account"], project)
#
#     @classmethod
#     def initialize_job(cls, job_id, job_status, upload_id=None, upload_status=None):
#         logger.debug("job_id: %s", job_id)
#         logger.debug("job_status: %s", job_status)
#         logger.debug("upload_id: %s", upload_id)
#         logger.debug("upload_status: %s", upload_status)
#
#         # GET Job
#         job_params = {"projection": ",".join(['status', 'jid', 'upload'])}
#         job = cls._get_job(job_id, params=job_params)
#         logger.debug("job: %s", job)
#         assert job
#
#
#         if upload_id != None:
#             # GET Upload
#             upload_params = {"projection": "status"}
#             upload = cls._get_upload(upload_id, params=upload_params)
#             logger.debug("upload: %s", upload)
#             assert upload
#
#         else:
#             upload = None
#
#
#         # PUT Job status
#         logger.info("Setting Job status..")
#         cls._put_job(job_id, {"status": job_status})
#
#         # PUT Upload status
#         if not upload:
#             logger.warning("No Upload found for Job: %s", job_id)
#         else:
#             logger.info("Setting Upload status..")
#             cls._put_upload(upload_id, {"status": upload_status})
#
#
#
#     @classmethod
#     @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
#     def _get_job(cls, job_id, params=None):
#         return api_client.get_job(job_id, params=params)
#
#     @classmethod
#     @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
#     def _post_job(cls, attributes):
#         return api_client.post_job(attributes)
#
#     @classmethod
#     @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
#     def _put_job(cls, job_id, attributes):
#         return api_client.put_job(job_id, attributes)
#
#     @classmethod
#     @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
#     def _get_upload(cls, upload_id, params=None):
#         return api_client.get_upload(upload_id, params=params)
#
#     @classmethod
#     @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
#     def _put_upload(cls, upload_id, attributes):
#         return api_client.put_upload(upload_id, attributes)
#
#     @classmethod
#     @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
#     def post_upload(cls, attributes):
#         cls.validate_upload_attributes(**attributes)
#         return api_client.post_upload(attributes)
#
#
#
#
#
#     def get_upload_files(self):
#         '''
#         Resolve the "upload_paths" and "upload_file" arguments to return a single list
#         of paths.
#         '''
#         # begin a list of "raw" filepaths that will need to be processed (starting with the self.upload_paths)
#         raw_filepaths = list(self.upload_paths)
#
#         # if an upload file as been provided, parse it and add it's paths to the "raw" filepaths
#         if self.upload_file:
#             logger.debug("self.upload_file is %s", self.upload_file)
#             upload_files = self.parse_upload_file(self.upload_file)
#             raw_filepaths.extend(upload_files)
#
#         # Process the raw filepaths (to account for directories, image sequences, formatting, etc)
#         return file_utils.process_upload_filepaths(raw_filepaths)
#
#
#     def parse_upload_file(self, upload_filepath):
#         '''
#         Parse the given filepath for paths that are separated by commas, returning
#         a list of these paths
#         '''
#         with open(upload_filepath, 'r') as file_:
#             logger.debug('opening file')
#             return [line.strip() for line in file_.readlines]
#
#
#     @classmethod
#     def validate_upload_attributes(cls, owner, project, status, upload_files, total_size, metadata=None, location=None):
#         '''
#         upload_files*: dict
#         status*: str.
#         project*: str. id of the project entity
#         total_size* = int. total byes of all files in the upload
#         '''
#
#         required_args = [owner,
#                          upload_files,
#                          status,
#                          project,
#                          total_size]
#
#         for arg in required_args:
#             if arg == None:
#                 raise Exception("Upload is missing required %r argument" % arg)



class BadArgumentError(ValueError):
    pass


# def submit_job(args):
#     # convert the Namespace object to a dictionary
#     args_dict = vars(args)
#
#     # Set up logging
#     log_level_name = args_dict.get("log_level") or CONFIG.get("log_level")
#     log_level = loggeria.LEVEL_MAP.get(log_level_name)
#     log_dirpath = args_dict.get("log_dir") or CONFIG.get("log_dir")
#     set_logging(log_level, log_dirpath)
#
#     logger.debug('parsed_args is %s', args_dict)
#     submission = Submit(args_dict, raise_error=True)
#     print "submission", submission
#     if submission.error:
#         logger.error(submission.error)
#         sys.exit(1)
#     elif submission.response.status_code not in [201, 204]:
#         logger.error("Submission Failure. Response code: %r", submission.response.status_code)
#         sys.exit(1)
#     else:
#         logger.info("%s", submission.response.json())
#         logger.info("Submission Complete")

#
# def consume_args(**kwargs):
#     '''
#     "Consume" the provided keyword arguments. For arguments that have not been
#     provided, or arguments with None value, default to reasonable values.
#
#     '''
#     args = {}
#     args["chunk_size"] = resolve_arg(kwargs, 'chunk_size', 1)
#     args["command"] = resolve_arg(kwargs, 'cmd', "")
#     args["cores"] = resolve_arg(kwargs, 'cores', 8)
#     args["database_filepath"] = resolve_arg(kwargs, 'database_filepath', "")
#     args["docker_image"] = resolve_arg(kwargs, 'docker_image', "")
#     args["enforced_md5s"] = resolve_arg(kwargs, 'enforced_md5s', {})
#     args["environment"] = resolve_arg(kwargs, 'environment', {}, combine_config=True)
#     args["frame_range"] = resolve_arg(kwargs, 'frames', "")
#     args["job_title"] = resolve_arg(kwargs, 'job_title', "")
#     args["local_upload"] = resolve_arg(kwargs, 'local_upload', True)
#     args["location"] = resolve_arg(kwargs, 'location', "")
#     args["machine_flavor"] = resolve_arg(kwargs, 'machine_type', "standard")
#     args["max_instances"] = resolve_arg(kwargs, 'max_instances', 0)
#     metadata = resolve_arg(kwargs, 'metadata', {}, combine_config=True)
#     args["metadata"] = cast_metadata(metadata, strict=False)
#     args["metadata_id"] = resolve_arg(kwargs, 'metadata_id', "")
#     args["md5_caching"] = resolve_arg(kwargs, 'md5_caching', True)
#     args["notify"] = { "emails": resolve_arg(kwargs, 'notify', [], combine_config=True),
#                     "slack": resolve_arg(kwargs, 'slack_notify', [], combine_config=True)}
#     args["output_path"] = resolve_arg(kwargs, 'output_path', "")
#     args["owner"] = resolve_arg(kwargs, 'user', getpass.getuser())
#     args["priority"] = resolve_arg(kwargs, 'priority', 5)
#     args["project"] = resolve_arg(kwargs, 'project', "")
#     args["scout_frames"] = resolve_arg(kwargs, 'scout_frames', "")
#     args["software_package_ids"] = resolve_arg(kwargs, 'software_package_ids', [], combine_config=True)
#     args["upload_file"] = resolve_arg(kwargs, 'upload_file', "")
#     args["upload_only"] = resolve_arg(kwargs, 'upload_only', False)
#     args["upload_id"] = resolve_arg(kwargs, 'upload_id', "")
#     args["upload_paths"] = resolve_arg(kwargs, 'upload_paths', [], combine_config=True)
#     args["thread_count"] = resolve_arg(kwargs, "thread_count", 6)  # TODO:(lws): expose thread count in Submit command
#     args["instance_type"] = "n1-%s-%s" % (args["machine_flavor"], args["cores"])  # TODO:(lws)Get rid of the cores and machine flavor)
#     return args


# def consume_args(**kwargs):
#     '''
#     "Consume" the provided keyword arguments. For arguments that have not been
#     provided, or arguments with None value, default to reasonable values.
#     '''
#
#     print "kwargs", kwargs
#     # create an object to store args on (this is simply for convenience/shortant)
#     Args = namedtuple('args', ARG_TYPES.keys())
#     args = Args(**kwargs)
#     print args
#     print args._asdict()
#     args.chunk_size = resolve_arg(kwargs, 'chunk_size', 1)
#     args.command = resolve_arg(kwargs, 'cmd', "")
#     args.cores = resolve_arg(kwargs, 'cores', 8)
#     args.database_filepath = resolve_arg(kwargs, 'database_filepath', "")
#     args.docker_image = resolve_arg(kwargs, 'docker_image', "")
#     args.enforced_md5s = resolve_arg(kwargs, 'enforced_md5s', {})
#     args.environment = resolve_arg(kwargs, 'environment', {}, combine_config=True)
#     args.frame_range = resolve_arg(kwargs, 'frames', "")
#     args.instance_type = "n1-%s-%s" % (args.machine_flavor, args.cores)  # TODO:(lws)Get rid of the cores and machine flavor)
#     args.job_title = resolve_arg(kwargs, 'job_title', "")
#     args.local_upload = resolve_arg(kwargs, 'local_upload', True)
#     args.location = resolve_arg(kwargs, 'location', "")
#     args.machine_flavor = resolve_arg(kwargs, 'machine_type', "standard")
#     args.max_instances = resolve_arg(kwargs, 'max_instances', 0)
#     metadata = resolve_arg(kwargs, 'metadata', {}, combine_config=True)
#     args.metadata = args.cast_metadata(metadata, strict=False)
#     args.metadata_id = resolve_arg(kwargs, 'metadata_id', "")
#     args.md5_caching = resolve_arg(kwargs, 'md5_caching', True)
#     args.notify = { "emails": resolve_arg(kwargs, 'notify', [], combine_config=True),
#                     "slack": resolve_arg(kwargs, 'slack_notify', [], combine_config=True)}
#     args.output_path = resolve_arg(kwargs, 'output_path', "")
#     args.owner = resolve_arg(kwargs, 'user', getpass.getuser())
#     args.priority = resolve_arg(kwargs, 'priority', 5)
#     args.project = resolve_arg(kwargs, 'project', "")
#     args.scout_frames = resolve_arg(kwargs, 'scout_frames', "")
#     args.software_package_ids = resolve_arg(kwargs, 'software_package_ids', [], combine_config=True)
#     args.upload_file = resolve_arg(kwargs, 'upload_file', "")
#     args.upload_only = resolve_arg(kwargs, 'upload_only', False)
#     args.upload_id = resolve_arg(kwargs, 'upload_id', "")
#     args.upload_paths = resolve_arg(kwargs, 'upload_paths', [], combine_config=True)
#     args.thread_count = resolve_arg(kwargs, "thread_count", 6)  # TODO:(lws): expose thread count in Submit command
#     return args._asdict()



# def resolve_args(args):
#     '''
#     "Consume" the give arguments (which have been parsed by argparse).
#     For arguments that have not been specified by the user via the command
#     line, default to reasonable values.
#     If inherit_config is True, then default unspecified arguments to those
#     values found in the config.yml file.
#
#     1. Use the argument provided by the user via the command line.  Note that
#        this may be a non-True value, such as False or 0.  So the only way
#        to know whether the argument was provided by the user is to check
#        whether is value is not None (which implies that argparse arguments
#        should not be configured to give a default value when the user has
#        not specified them).
#
#    2. If the user has not provided the argument, and if inherit_config is
#       True, then use the value found in the config.
#
#    3. If inherit_config is False or the the value in the config doesn't
#       exist, then default to an empty or non-True value.
#
#     '''
#
#     argz["command"] = resolve_arg(args, 'cmd', "")
#
#     argz["cores"] = resolve_arg(args, 'cores', 8)
#     logger.debug("cores: %s", self.cores)
#
#     argz["database_filepath"] = resolve_arg(args, 'database_filepath', "")
#     logger.debug("database_filepath: %s", self.database_filepath)
#
#     argz["docker_image"] = resolve_arg(args, 'docker_image', "")
#     logger.debug("docker_image: %s", self.docker_image)
#
#     argz["enforced_md5s"] = resolve_arg(args, 'enforced_md5s', {})
#     logger.debug("enforced_md5s: %s", self.enforced_md5s)
#
#     argz["environment"] = resolve_arg(args, 'environment', {}, combine_config=True)
#     logger.debug("environment: %s", sstr(self.environment))
#
#     argz["frame_range"] = resolve_arg(args, 'frames', "")
#     logger.debug("frame_range: %s", self.frame_range)
#
#     argz["job_title"] = resolve_arg(args, 'job_title', "")
#     logger.debug("job_title: %s", self.job_title)
#
#     argz["local_upload"] = resolve_arg(args, 'local_upload', True)
#     logger.debug("local_upload: %s", self.local_upload)
#
#     argz["location"] = resolve_arg(args, 'location', "")
#     logger.debug("location: %s", self.location)
#
#     argz["machine_flavor"] = resolve_arg(args, 'machine_type', "standard")
#     logger.debug("machine_flavor: %s", self.machine_flavor)
#
#     metadata = resolve_arg(args, 'metadata', {}, combine_config=True)
#     argz["metadata"] = self.cast_metadata(metadata, strict=False)
#
#
#     argz["metadata_id"] = resolve_arg(args, 'metadata_id', "")
#
#     argz["md5_caching"] = resolve_arg(args, 'md5_caching', True)
#
#     argz["output_path"] = resolve_arg(args, 'output_path', "")
#
#     argz["priority"] = resolve_arg(args, 'priority', 5)
#
#     argz["project"] = resolve_arg(args, 'project', "")
#
#
#     argz["scout_frames"] = resolve_arg(args, 'scout_frames', "")
#
#     argz["software_package_ids"] = resolve_arg(args, 'software_package_ids', [], combine_config=True)
#
#     argz["upload_file"] = resolve_arg(args, 'upload_file', "")
#
#     argz["upload_only"] = resolve_arg(args, 'upload_only', False)
#
#     argz["max_instances"] = resolve_arg(args, 'max_instances', 0)
#
#     argz["chunk_size"] = resolve_arg(args, 'chunk_size', 1)
#
#     argz["upload_id"] = resolve_arg(args, 'upload_id', "")
#
#     argz["upload_paths"] = resolve_arg(args, 'upload_paths', [], combine_config=True)
#
#     argz["owner"] = resolve_arg(args, 'user', getpass.getuser())
#
#     argz["notify"] = { "emails": resolve_arg(args, 'notify', [], combine_config=True),
#                     "slack": resolve_arg(args, 'slack_notify', [], combine_config=True)}
#
#     argz["thread_count"] = resolve_arg(args, "thread_count", 6)  # TODO:(lws): expose thread count in Submit command
#
#     argz["instance_type"] = "n1-%s-%s" % (self.machine_flavor, self.cores)  # TODO:(lws)Get rid of the cores and machine flavor)


def resolve_arg(args, arg_name, default, read_config=True, combine_config=False):
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
    if arg_name in CONFIG and read_config:
        config_value = CONFIG[arg_name]

        # If the arg value is  None, it indicates that the arg was not
        # explicitly set. And if the config lists a value,then use it.
        # Note that it's valid that the config may state a non-True value (i.e. 0, False, etc)
        if arg_value == None:
            return config_value

        # IF we're here, then it means that the arg_Value is not None, so
        # simple check whether we're combining its value with the the config
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



def cast_cli_args(**kwargs):
    '''
    Cast/resolbe human friendly command line args to proper arguments for
    submission classes 
    '''
    logger.info("Reconciling upload files")
    kwargs["upload_files"] = get_upload_files(kwargs["upload_paths"],
                                                   kwargs["upload_file"], {})
    kwargs["project"] = "%s|%s" % (CONFIG["account"], kwargs["project"])
    return kwargs

def get_upload_files(upload_paths, upload_file, enforced_md5s):
    '''
    Parse/resolve all of the given upload paths (directories, path expressions
    files) to full filepaths.
    Generate a dictionary where the key is the filepath, and the value is
    the md5 of the file (or None if there is no md5 enforcement) 
    '''

    # if an upload file as been provided, parse it and add it's paths to the "raw" filepaths
    if upload_file:
        logger.debug("self.upload_file is %s", upload_file)
        parsed_filepaths = parse_upload_file(upload_file)
        upload_paths.extend(parsed_filepaths)

    processed_filepaths = file_utils.process_upload_filepaths(upload_paths)

    # Convert the list of filepaths into a dictionary where all the values are None
    upload_files = dict([(path, None) for path in processed_filepaths])

    # process the enforced filepaths to ensure they exist/conform
    for md5, filepath in enforced_md5s.iteritems():
        processed_filepath = file_utils.process_upload_filepath(filepath)
        # this will always be a list. make sure that only one file is in this list
        # so that a single md5 value can corellate to it
        assert len(processed_filepath) == 1, "Found more than one file for path: %s\nGot: %s" % (filepath, processed_filepath)
        upload_files[processed_filepath[0]] = md5

    return upload_files


def parse_upload_file(upload_filepath):
    '''
    Parse the given filepath for paths that are separated by commas, returning
    a list of these paths
    '''
    with open(upload_filepath, 'r') as file_:
        logger.debug('opening file')
        return [line.strip() for line in file_.readlines()]



class ThreadedWork(object):
    MAX_THREADS = 2

    def __init__(self, work_queue, thread_count=None):
        self._work_queue = work_queue
        self._output_queue = Queue.Queue()
        self._error_queue = Queue.Queue()
        self._thread_count = thread_count or self.MAX_THREADS
#         self._thread_count = thread_count if thread_count != None else multiprocessing.cpu_count() * 2

    @common.dec_function_timer
    def run(self):
        threads = []
        for thread_num in range(min(self._work_queue.qsize(), self._thread_count)):
            t = threading.Thread(target=self._work)
            threads.append(t)
            t.start()

        while [thread.isAlive() for thread in threads]:
            logger.debug("waiting for thread: %s", thread.name)
            time.sleep(1)
        [thread.join() for thread in threads]

    def _work(self):
        try:
            work = self._work_queue.get_nowait()
        except Queue.Empty:
            logger.debug("no work. exiting thread")
            return

        try:
            result = self.work(work)
            self._output_queue.put((work, result))
        except:
            self._error_queue.put((work, traceback.format_exc()))
            logger.exception("Caught Exception:\n")

        print "calling self._work_"
        self._work()

    def work(self, *args, **kwargs):
        raise NotImplementedError


class UpdateTasks(ThreadedWork):

    def work(self, work):
        while True:
            logger.debug("work: %s", work)
            task_id, attributes = work
            logger.debug("task_id: %r", task_id)
            logger.debug("attributes: %r", attributes)
            return self.put_task(task_id, **attributes)

    @common.dec_retry(retry_exceptions=api_client.CONNECTION_EXCEPTIONS, tries=5)
    def put_task(self, task_id, **attributes):
        logger.debug("Putting Task %s", task_id)
        return api_client.put_task(task_id, **attributes)



# task_ids = [
# 6705309988945920,
# 4559063291527168,
# 5684963198369792,
# 5122013244948480,
# 6247913151791104,
# 4840538268237824,
# 5966438175080448,
# 5403488221659136,
# 6529388128501760,
# 4699800779882496,
# 5825700686725120,
# 5262750733303808,
# 6388650640146432,
# 4981275756593152,
# 6107175663435776,
# 5544225710014464,
# 6670125616857088,
# 4629432035704832,
# 5755331942547456,
# 5192381989126144,
# 6318281895968768,
# 4910907012415488,
# 6036806919258112,
# 5473856965836800,
# 6599756872679424,
# 4770169524060160,
# 5896069430902784,
# 5333119477481472,
# 6459019384324096,
# 5051644500770816,
# 6177544407613440,
# 5614594454192128,
# 6740494361034752,
# 4515082826416128,
# 5640982733258752,
# 5078032779837440,
# 6203932686680064,
# 4796557803126784,
# 5922457709969408,
# 5359507756548096,
# 6485407663390720,
# 4655820314771456,
# 5781720221614080,
# 5218770268192768,
# 6344670175035392,
# 4937295291482112,
# 6063195198324736,
# 5500245244903424,
# 6626145151746048,
# 4585451570593792,
# 5711351477436416,
# 5148401524015104,
# 6274301430857728,
# 4866926547304448,
# 5992826454147072,
# 5429876500725760,
# 6555776407568384,
# 4726189058949120,
# 5852088965791744,
# 5289139012370432,
# 6415038919213056,
# 5007664035659776,
# 6133563942502400,
# 5570613989081088,
# 6696513895923712,
# 4550267198504960,
# 5676167105347584,
# 5113217151926272,
# 6239117058768896,
# 4831742175215616,
# 5957642082058240,
# 5394692128636928,
# 6520592035479552,
# 4691004686860288,
# 5816904593702912,
# 5253954640281600,
# 6379854547124224,
# 4972479663570944,
# 6098379570413568,
# 5535429616992256,
# 6661329523834880,
# 4620635942682624,
# 5746535849525248,
# 5183585896103936,
# 6309485802946560,
# 4902110919393280,
# 6028010826235904,
# 5465060872814592,
# 6590960779657216,
# 4761373431037952,
# 5887273337880576,
# 5324323384459264,
# 6450223291301888,
# 5042848407748608,
# 6168748314591232,
# 5605798361169920,
# 6731698268012544,
# 4532675012460544,
# 5658574919303168,
# 5095624965881856]
#
# task_info = [(task_id, "status") for task_id in task_ids]

#
#     print "submission", submission
#     if submission.error:
#         logger.error(submission.error)
#         sys.exit(1)
#     elif submission.response.status_code not in [201, 204]:
#         logger.error("Submission Failure. Response code: %r", submission.response.status_code)
#         sys.exit(1)
#     else:
#         logger.info("%s", submission.response.json())
#         logger.info("Submission Complete")

