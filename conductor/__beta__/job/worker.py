import logging

import conductor

from . import job

LOG = logging.getLogger(__name__)

class WorkerJobError(job.JobError):
    pass

class WorkerJob(job.Job):
    pass

class DeadlineWorkerJobError(WorkerJobError):
    pass

class DeadlineWorkerJob(WorkerJob):

    POST_TASK_SCRIPT_PATH = '/opt/thinkbox/deadline/10/deadline10.1/bin/shutdown_conductor_instance.py'
    
    def __init__(self, *args , **kwargs):
    
        super(WorkerJob, self).__init__(*args, **kwargs)
        
        self.output_path = "/tmp"
    
        self.job_title = "Deadline Worker"
        self.instance_count = 1
        
        # Hard-coded to work with Maya for the time being
        self.software_packages_ids = None
        
        self.cmd = "/opt/thinkbox/deadline/10/deadline10.1/bin/launch_deadline.sh"
        self.docker_image = "gcr.io/images-production/conductor_docker_base:deadline_debian"
        self.deadline_proxy_root = None
        self.deadline_ssl_certificate = None
        self.deadline_use_ssl = False
        self.deadline_client_version = "10.1.1.3"
        self.deadline_group_name = None
        
    def _get_task_data(self):
        task_data = []
        
        # Create a task for every instance that's been requested
        for instance_number in range(1, self.instance_count+1):
            task_data.append({"frames": str(instance_number), "command": self.cmd})
        
        return task_data
    
    def set_deadline_ssl_certificate(self, path):
        self.deadline_ssl_certificate =  conductor.lib.file_utils.conform_platform_filepath(conductor.lib.file_utils.strip_drive_letter(path))
        self.upload_paths.append(path)
    
    def _get_environment(self):
        
        self.environment['CONDUCTOR_PATHHELPER'] = '0'
        self.environment['CONDUCTOR'] = '1'
        self.environment['CONDUCTOR_DEADLINE_GROUP_NAME'] = self.deadline_group_name 
        
        self.environment['DCONFIG_ProxyUseSSL'] = str(self.deadline_use_ssl).lower()
        self.environment['CONDUCTOR_DEADLINE_CLIENT_VERSION'] = self.deadline_client_version        
        
        if self.deadline_use_ssl:
            self.environment['DCONFIG_ProxySSLCertificate'] = self.deadline_ssl_certificate
            self.environment['DCONFIG_ProxyRoot'] = "{};{}".format(self.deadline_proxy_root, self.deadline_ssl_certificate)
            
        else:
            self.environment['DCONFIG_ProxyRoot'] = self.deadline_proxy_root

        return super(WorkerJob, self)._get_environment()
    
    def validate_job(self):
        
        if self.deadline_proxy_root is None:
            raise DeadlineWorkerJobError("deadline_proxy_root has not been set. This must be the <hostname>:<port> of your Deadline RCS")
        
        if self.deadline_ssl_certificate is None:
            raise DeadlineWorkerJobError("deadline_ssl_certificate has not been set. This must be the local path to your Deadline client certificate")
        
        return True           
