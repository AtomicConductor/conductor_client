import os
import logging

import conductor

from . import job

LOG = logging.getLogger(__name__)


class DeadlineToConductorPackageMapperError(Exception):
    pass


class WorkerJobError(job.JobError):
    pass


class DeadlineWorkerJobError(WorkerJobError):
    pass


class WorkerJob(job.Job):
    pass


class DeadlineWorkerJob(WorkerJob):
    
    POST_TASK_SCRIPT_PATH = '/opt/thinkbox/deadline/{major_version}/deadline{version}/conductor/shutdown_conductor_instance.py'
    DEFAULT_CMD = "launch_deadline.sh"
    DEFAULT_WORKER_VERSION = "10.1.12.1"
    
    def __init__(self, *args , **kwargs):
    
        super(WorkerJob, self).__init__(*args, **kwargs)
        
        self.output_path = "/tmp"
    
        self.job_title = "Deadline Worker"
        self.instance_count = 1
        
        self.cmd = self.DEFAULT_CMD
        self.deadline_proxy_root = None
        self.deadline_ssl_certificate = None
        self.deadline_use_ssl = True
        self.deadline_client_version = self.DEFAULT_WORKER_VERSION
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

        self.environment['CONDUCTOR_DEADLINE_GROUP_NAME'] = self.deadline_group_name         
        self.environment['DCONFIG_ProxyUseSSL'] = str(self.deadline_use_ssl).lower()
        self.environment['CONDUCTOR_DEADLINE_CLIENT_VERSION'] = self.deadline_client_version
        self.environment['DCONFIG_ProxyRoot'] = self.deadline_proxy_root
        
        if self.deadline_use_ssl:
            self.environment['DCONFIG_ProxySSLCertificate'] = self.deadline_ssl_certificate
        
        env = super(WorkerJob, self)._get_environment()
        
        env['CONDUCTOR_DEADLINE_SKIP_ENV_VAR_DUMP'] = "0"
        env['CONDUCTOR_DEADLINE_SHOW_WATCHER_DEBUG'] = "1"

        return env 
    
    def validate_job(self):
        
        if self.deadline_proxy_root is None:
            raise DeadlineWorkerJobError("deadline_proxy_root has not been set. This must be the <hostname>:<port> of your Deadline RCS")
        
        if self.deadline_ssl_certificate is None:
            raise DeadlineWorkerJobError("deadline_ssl_certificate has not been set. This must be the local path to your Deadline client certificate")
        
        return True
    
    def submit_job(self):                
        
        deadline_package = conductor.lib.package_utils.get_host_package("deadline", self.deadline_client_version, strict=False)['package']
        self.software_packages_ids.append(deadline_package)
        
        return super(DeadlineWorkerJob, self).submit_job()
    
    def get_post_task_script_path(self):
        
        major_version = self.deadline_client_version.split(".")[0]         
        return self.POST_TASK_SCRIPT_PATH.format(major_version=major_version, version=self.deadline_client_version)
            

class DeadlineToConductorPackageMapper(object):
    
    PLUGIN_TO_PACKAGE_MAPPING = {}
    
    @classmethod
    def map(cls, deadline_job):
        
        plugin_name = deadline_job.GetJobInfoKeyValue("Plugin")
        map_class = cls.PLUGIN_TO_PACKAGE_MAPPING.get(plugin_name)

        if map_class is None:
            raise DeadlineToConductorPackageMapperError("No class has been registered for the Deadline plugin '{}'".format(plugin_name))
        
        LOG.debug("Using mapping class '{}' for plugin '{}'".format(map_class, plugin_name))
        
        return map_class.map(deadline_job)

    @classmethod
    def register(cls, mapping_class):
        
        for plugin in mapping_class.DEADLINE_PLUGINS:
            
            if plugin in cls.PLUGIN_TO_PACKAGE_MAPPING:
                raise DeadlineToConductorPackageMapperError("The plugin '{}' has already been registered with the class {}".format(cls.PLUGIN_TO_PACKAGE_MAPPING[plugin]))
            
            LOG.debug("Registering mapping plugin '{}' to class '{}'".format(plugin, mapping_class))
            cls.PLUGIN_TO_PACKAGE_MAPPING[plugin] = mapping_class
    

class Maya(object):
    
    DEADLINE_PLUGINS = ["MayaCmd"]
    PRODUCT_NAME = "maya-io"
    
    product_version_map = {"2018": "Autodesk Maya 2018.6"}
    render_version_map = {'arnold': {'plugin': 'arnold-maya', 'version': 'latest'},
                          'vray': {'plugin': 'v-ray-maya', 'version': 'latest'},
                          'renderman': {'plugin': 'renderman-maya', 'version': 'latest'}}
    
    @classmethod
    def map(cls, deadline_job):
        
        package_ids = []
        
        render_name = deadline_job.GetJobPluginInfoKeyValue("Renderer").lower()
        major_version = deadline_job.GetJobPluginInfoKeyValue("Version")
        product_version = cls.product_version_map[major_version]
        
        if render_name == "File":
            raise DeadlineToConductorPackageMapperError("Integration doesn't support 'File', please explicitly choose a renderer in the MayaCmd plugin properties")
        
        if render_name not in cls.render_version_map:
            raise DeadlineToConductorPackageMapperError("The render '{}' is not currently support by the Conductor Deadline integration.\n{}".format(render_name, cls.render_version_map))
        
        host_package = conductor.lib.package_utils.get_host_package(cls.PRODUCT_NAME, product_version, strict=False)
        LOG.debug("Found package: {}".format(host_package))
        package_ids.append(host_package.get("package"))
        
        conductor_render_plugin = cls.render_version_map[render_name]
        
        if conductor_render_plugin['version'] == 'latest':
            render_plugin_versions = host_package[conductor_render_plugin['plugin']].keys()
            render_plugin_versions.sort()
            render_plugin_version = render_plugin_versions[-1]
            
        else:
            if conductor_render_plugin['version'] not in conductor_render_plugin['plugin'].keys():
                raise DeadlineToConductorPackageMapperError("Unable to find {plugin} version '{version}' in Conductor packages".format(conductor_render_plugin))
            
            render_plugin_version = conductor_render_plugin['plugin']
            
        LOG.debug("Using render: {} {} {}".format(conductor_render_plugin, render_plugin_version, host_package[conductor_render_plugin['plugin']][render_plugin_version]))
        
        render_package_id = host_package[conductor_render_plugin['plugin']][render_plugin_version]
        package_ids.append(render_package_id)

        return package_ids
    
    
DeadlineToConductorPackageMapper.register(Maya)            
        
