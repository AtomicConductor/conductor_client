import logging
import os

import conductor.lib.api_client
import conductor.lib.conductor_submit as conductor_submit
import conductor.lib.package_utils


LOG = logging.getLogger(__name__)

class JobError(Exception):
    pass

class Job(object):
    
    def __init__(self):
    
        self.upload_paths = []
        self.software_packages_ids = []
        self.owner = 'bob'
        self.priority = 5
        self.location = ""
        self.instance_type = "n1-standard-8"
        self.metadata = {}
        self.local_upload = True
        self.auto_retry_policy = {}
        self.preemptible = True
        self.chunk_size = 1
        self.project = "default"
        self.output_path = ""
        self.job_title = ""
        self.docker_image = ""
        self._dependencies = None
        self.environment = {}
        
        self._dependency_scan_enabled = True
        self.conductor_job_id = None
                
    def _get_task_data(self):
        pass
    
    def _get_frame_range(self):
        pass
    
    def _get_environment(self):
        
        packages = [package for package in conductor.lib.api_client.request_software_packages() if package["package_id"] in self.software_packages_ids]
        return conductor.lib.package_utils.merge_package_environments(packages, base_env=self.environment)
    
    def get_output_path(self):
        return self.output_path
    
    def scan_for_dependencies(self):
        return []
    
    def get_dependencies(self):
        
        if self._dependencies is None and self._dependency_scan_enabled:            
            self._dependencies = self.scan_for_dependencies()
            
        return self._dependencies + self.upload_paths

    def submit_job(self):
        
        self.validate_job()
        
        data = { "upload_paths": self.get_dependencies(),
                 "software_package_ids": self.software_packages_ids, 
                 "tasks_data": self._get_task_data(), 
                 "owner": self.owner, 
                 "frame_range": self._get_frame_range(),
                 "environment": self._get_environment(), 
                 "priority": self.priority,
                 "location": self.location, 
                 "instance_type": self.instance_type, 
                 "preemptible": self.preemptible, 
                 "metadata": self.metadata, 
                 "local_upload": self.local_upload, 
                 "autoretry_policy": self.auto_retry_policy,
                 "chunk_size": self.chunk_size, 
                 "project": self.project,
                 "output_path": self.get_output_path(), 
                 "job_title": self.job_title}
        
        if self.docker_image:
            data["docker_image"] = self.docker_image
        
        for key, value in os.environ.items():
            if key.startswith("CONDUCTOR_JOBPARM_"):
                job_parm_key = key.replace("CONDUCTOR_JOBPARM_", "")
                
                if value.lower() == "true":
                    value = True
                
                elif value.lower() == "false":
                    value = False
                    
                try:
                    value = int(value)
                except ValueError:
                    pass
                    
                data[job_parm_key.lower()] = value
        
        LOG.debug("Job Parameters:")
        for k, v in data.iteritems():
            LOG.debug("  {}: '{}'".format(k, v))
        
        submitter = conductor_submit.Submit(data)
        
        response, response_code = submitter.main()
        LOG.debug("Response Code: %s", response_code)
        LOG.debug("Response: %s", response)
         
        if response_code in [201, 204]:
            LOG.info("Submission Complete")
 
        else:
            LOG.error("Submission Failure. Response code: %s", response_code)
            raise JobError("Submission Failure. Response code: %s", response_code)
 
        self.conductor_job_id = response['jobid']
         
        return self.conductor_job_id
    
    @classmethod
    def get_klass(cls, cmd):
        '''
        A factory helper method to choose the appropriate child class based on
        the provided command.
        
        :param cmd: The command to get the corresponding class for
        :type cmd: str
        
        :retrun: The Job that matches the given command
        :rtype: A child class of :class: `Job`
        '''
        
        from . import MayaRenderJob
        
        if "Render" in cmd:
            return MayaRenderJob
        
        else:
            raise JobError("Unable to match the command '{}' to an appropriate class".format(cmd))
