#!/usr/bin/env python
"""This script runs on a cloud render instance to communicate
with the Conductor app and do renders. """

import copy
import os
import sys
import logging
import random
import subprocess
import urllib2
import base64
import json
import time
import traceback
import shutil
import startup_lib
import sys

# MAYA CONSTANTS
MAYA_DIR = "/usr/autodesk/maya2015-x64"
MAYA_VRAY_DIR = MAYA_DIR + "/vray"
MAYA_VRAY_SETUP_DIR = "/usr/ChaosGroup/V-Ray/Maya2015-x64"  # This directory should probably be merged with MAYA_VRAY_DIR (see the way AF has it setup).  As-is, this is super confusing
MAYA_VRAY_PLUGINS_DIR = MAYA_VRAY_DIR + "/vrayplugins"  # Note the AF's vray directory looks a lot different: /opt/chaosgroup/vray/vray_adv_maya2015-30001/maya2015-x64/vray/vrayplugins
MAYA_VRAY_SCRIPTS_DIR = MAYA_VRAY_DIR + "/scripts"

# GOLAEM CONSTANTS
GOLAEM_DIR = '/opt/golaem/GolaemCrowd-4.1.2-Maya2015'
GOLAEM_LIB_DIR = GOLAEM_DIR + '/lib'
GOLAEM_PROCEDURALS_DIR = GOLAEM_DIR + '/procedurals'
GOLAEM_LICENSE_SRVR = os.environ['GOLAEM_LICENSE_SERVER']

# KATANA CONSTANTS
KATANA_DIR = "/opt/thefoundry/katana/katana2.0v1"
VRAY_KATANA_DIR = "/opt/chaosgroup/vray/vray_adv_30501-25893_katana_2_0_linux_x64"
FOUNDRY_LICENSE_SRVR = os.environ['FOUNDRY_LICENSE_SERVER']

# NUKE CONSTANTS
PEREGRINEL_LICENSE_SRVR = os.environ['PEREGRINEL_LICENSE_SRVR']  # TODO: this needs to updated/confirmed

DOCKER_REGISTRY = os.environ['DOCKER_REGISTRY']
DEFAULT_OUT_DIRS = ['/tmp/render_output']


def append_env_var(var_name, var_value, seperator=os.pathsep):
    '''
    Append the given value (var_value) to the given environment variable (var_name).
    Return the environment variable's final value.
    '''
    existing = os.environ.get(var_name, "")
    final_val = os.pathsep.join([existing, var_value]).strip(os.pathsep)
    os.environ[var_name] = final_val
    return final_val


def setup_maya_env():
    '''
    Set environment variables for maya.  This also includes maya plugins such as:
        - Golaem
        - Vray
    '''
    # TODO: REMOVE THIS- this is so that the we can run "maya_fix_paths.py" for windows paths.
    append_env_var("PYTHONPATH", '/opt/conductor/python')


    #### LD_LIBRARY_PATH ####  TODO: Not sure if we actually have to set all of these
    append_env_var('LD_LIBRARY_PATH', MAYA_DIR + "/lib")
    append_env_var('LD_LIBRARY_PATH', MAYA_DIR + "/plug-ins/bifrost/lib")
    append_env_var('LD_LIBRARY_PATH', MAYA_DIR + "/plug-ins/fbx/plug-ins")
    append_env_var('LD_LIBRARY_PATH', MAYA_DIR + "/plug-ins/substance/lib")
    append_env_var('LD_LIBRARY_PATH', MAYA_DIR + "/plug-ins/xgen/lib")

    #### GOLAEM #####
    os.environ['GLM_CROWD_HOME'] = GOLAEM_DIR
    os.environ['golaem_LICENSE'] = GOLAEM_LICENSE_SRVR
    append_env_var('MAYA_MODULE_PATH', GOLAEM_DIR)
    append_env_var('MI_CUSTOM_SHADER_PATH', GOLAEM_PROCEDURALS_DIR)
    append_env_var('LD_LIBRARY_PATH', GOLAEM_LIB_DIR)
    append_env_var('VRAY_FOR_MAYA2015_PLUGINS_x64', GOLAEM_LIB_DIR)
    append_env_var('VRAY_FOR_MAYA2015_PLUGINS_x64', GOLAEM_PROCEDURALS_DIR)
    append_env_var('VRAY_FOR_MAYA_SHADERS', GOLAEM_DIR + '/shaders')
    append_env_var('VRAY_PLUGINS_x64', GOLAEM_PROCEDURALS_DIR)

    #### VRAY #####
    append_env_var('MAYA_SCRIPT_PATH', MAYA_VRAY_SCRIPTS_DIR)
    append_env_var('MAYA_PLUG_IN_PATH', MAYA_VRAY_DIR + '/plugins')
    append_env_var('PATH', MAYA_VRAY_DIR + '/bin')
    append_env_var('PYTHONPATH', MAYA_VRAY_SCRIPTS_DIR)
    append_env_var('VRAY_FOR_MAYA2015_MAIN_x64', MAYA_VRAY_DIR)
    append_env_var('VRAY_FOR_MAYA2015_PLUGINS_x64', MAYA_VRAY_PLUGINS_DIR)
    append_env_var('VRAY_OSL_PATH_MAYA2015_x64', MAYA_VRAY_SETUP_DIR + '/opensl')
    append_env_var('VRAY_PLUGINS_x64', MAYA_VRAY_PLUGINS_DIR)
    append_env_var('VRAY_TOOLS_MAYA2015_x64', MAYA_VRAY_DIR + '/bin')


def setup_katana_env():
    '''
    Setup environment variables for Katana
    '''

    # Katana requires that LC_ALL to be set.  Apparently it's a "localization"
    # setting (used by many applications). The "C" indicates it's for "computers"
    # (rather than humans), which ultimately results in using bytes rather than ascii...or some shit.
    os.environ['LC_ALL'] = "C"

    # Set the licence for Katana (the Foundry)
    os.environ['foundry_LICENSE'] = FOUNDRY_LICENSE_SRVR

    # Add katana's own Resource's directory
    append_env_var('KATANA_RESOURCES', KATANA_DIR + "/plugins/Resources")


    ### VRAY ####

    # Add Vray's katana directory
    append_env_var('KATANA_RESOURCES', VRAY_KATANA_DIR)

    append_env_var('VRAY_FOR_KATANA_PLUGINS_x64', VRAY_KATANA_DIR + "/vrayplugins")


def setup_nuke_env():
    '''
    Setup environment variables for Nuke
    '''

    os.environ['LC_ALL'] = "C"
    os.environ['peregrinel_LICENSE'] = PEREGRINEL_LICENSE_SRVR



def log_env(logger):
    '''
    Log out all environment variables in readable format (from os.environ)
    '''
    logger.debug("-------------------------- Environment -----------------------------")
    for var, val in sorted(os.environ.iteritems()):
        logger.debug("%s=%s", var, val)
    logger.debug("----------------------- End Environment-----------------------------")


class Render(startup_lib.StartupScript):
    """ Script to run on instances to perform renders.
        Inherited class attributes are
            self.logger
            self.account
            self.metadata
            self.tags
    """

    def __init__(self, logger):
        super(Render, self).__init__(logger)
        self.starttime = time.time()
        self.min_running_time = 600
        self.resource = self.metadata['resource']
        self.status = "success"
        self.running = True
        self.jid = None
        self.tid = None
        self.command = None
        self.out_dirs = copy.copy(DEFAULT_OUT_DIRS)
        self.frame = None
        self.fake_root = "/tmp/fake_root"
        self.fake_base_dirs = []
        self.custom_environment = {}

    def set_vray_license(self):
        """ Set the vray license server to the hosted license server """


        # Set the license server the old way as a backup
        # TODO: Let's get rid of this section ASAP.  Is there any need for it?
        os.environ['HOME'] = "/home/conductor"
        self.logger.debug("Ensure that vray license server is setup for rendering user.")
        lic_server = '10.0.1.100'
        vray_lic_port = '30304'
        set_service_cmd = '/usr/autodesk/maya2015-x64/vray/bin/setvrlservice'\
            ' -server=%s -port=%s' % (lic_server, vray_lic_port)
        subprocess.check_call(set_service_cmd, shell=True)



        # Drop a license file in the Home directory pointing it to the hosted
        # license server.
        # Note that the vray plugin defaults to looking in the current $HOME
        # directory for it's license file, e.g. $HOME/.ChaosGroup/vrlclient.xml.
        # Because it's apparently impossible to explictly indicate to vray as to
        # where it should look for the license file, we must go through a silly
        # process of setting the $HOME variable to some random place and creating
        # the necessary ChaosGroup subdirectory, etc.
        # TODO: There has got to be a better way to to set the license up than
        # this.  More research needed.  Note that setting the VRAY_AUTH_CLIENT_FILE_PATH
        # environment variable to point to the license file actually made things worse :(
        os.environ['HOME'] = "/home/conductor"
        CHAOSGROUP_LICENSE_SERVER_IP = os.environ['CHAOSGROUP_LICENSE_SERVER_IP']
        CHAOSGROUP_LICENSE_SERVER_PORT = os.environ['CHAOSGROUP_LICENSE_SERVER_PORT']
        CHAOSGROUP_LICENSE_SERVER_USER = os.environ['CHAOSGROUP_LICENSE_SERVER_USER']
        CHAOSGROUP_LICENSE_SERVER_PASSWORD = os.environ['CHAOSGROUP_LICENSE_SERVER_PASSWORD']
        home = "/home/conductor"
        lic_text_unformatted = """<VRLClient>
    <LicServer>
        <Host>lsg.chaosgroup.com</Host>
        <Port>{CHAOSGROUP_LICENSE_SERVER_PORT}</Port>
        <Host1>{CHAOSGROUP_LICENSE_SERVER_IP}</Host1>
        <Port1>{CHAOSGROUP_LICENSE_SERVER_PORT}</Port1>
        <Host2></Host2>
        <Port2>{CHAOSGROUP_LICENSE_SERVER_PORT}</Port2>
        <!Proxy></!Proxy>
        <!ProxyPort>0</!ProxyPort>
        <User>{CHAOSGROUP_LICENSE_SERVER_USER}</User>
        <Pass>{CHAOSGROUP_LICENSE_SERVER_PASSWORD}</Pass>
    </LicServer>
</VRLClient>"""
        lic_text = lic_text_unformatted.format(
            CHAOSGROUP_LICENSE_SERVER_IP=CHAOSGROUP_LICENSE_SERVER_IP,
            CHAOSGROUP_LICENSE_SERVER_PORT=CHAOSGROUP_LICENSE_SERVER_PORT,
            CHAOSGROUP_LICENSE_SERVER_USER=CHAOSGROUP_LICENSE_SERVER_USER,
            CHAOSGROUP_LICENSE_SERVER_PASSWORD=CHAOSGROUP_LICENSE_SERVER_PASSWORD)
        chaos_dirpath = os.path.join(home, '.ChaosGroup')
        if not os.path.exists(chaos_dirpath):
            self.logger.debug("Path does not exist. Creating: %s", chaos_dirpath)
            os.makedirs(chaos_dirpath)

        chmod_cmd = 'chmod 777 %s' % chaos_dirpath
        self.logger.debug(chmod_cmd)
        subprocess.check_call(chmod_cmd, shell=True)

        license_filepath = os.path.join(chaos_dirpath, 'vrlclient.xml')

        # If the license already exists, change the permissions to ensure that
        # we can write over it.
        # TODO: Why are we checking that this file exists or not? We should know.
        # This is a waste of space/time
        if os.path.exists(license_filepath):
            chmod_cmd = 'chmod 777 %s' % license_filepath
            self.logger.debug(chmod_cmd)
            subprocess.check_call(chmod_cmd, shell=True)

        # Write the license file to the home directory
        self.logger.debug("Writing vray license to disk: %s", license_filepath)
        file_obj = open(license_filepath, 'w')
        file_obj.write(lic_text)
        file_obj.close()


    #  Get a list of files that we were uploading...
    def get_upload_files(self):
        #  Get the Upload object from the data store
        endpoint = "%s/api/files/get_upload_files/%s" % (self.conductor_url, self.jid)
        self.logger.debug('connecting to %s' % endpoint)
        request = urllib2.Request(endpoint)
        base64string = base64.encodestring('%s:%s' % (
            startup_lib.username,
            startup_lib.password)).replace('\n', '')

        request.add_header("Authorization", "Basic %s" % base64string)
        request.add_header('Content-Type', 'application/json')

        response = urllib2.urlopen(request)
        response_dict = json.loads(response.read())
        self.logger.info("response is %s" % response_dict)
        return response_dict['uploads'], response_dict['response_code']


    #  Create links to any files that are needed for this job...
    def create_job_links(self):
        self.logger.info("Creating job links")
        self.upload_files, response_code = self.get_upload_files()

        if response_code == 200:
            self.logger.info("No upload files returned. No links being created")
            return
        else:
            self.logger.info("Received upload files: %s" % (self.upload_files))

        #  Iterate through each file
        for upload_file in self.upload_files:

            md5_hash = self.upload_files[upload_file]
            #  Figure out what the phony root mount point is for each file
            #  by getting the first part of the directory path
            base_dir = upload_file
            while os.path.dirname(base_dir) != '/':
                base_dir = os.path.dirname(base_dir)
            self.logger.info("Base directory mount point is %s" % (base_dir))

            #  The location of the link to gluster will be based out of the fake
            #  root directory for ease of cleanup
            upload_file = "%s%s" % (self.fake_root, upload_file)
            dest_dir = os.path.dirname(upload_file)
            self.logger.info("destination directory is %s" % (dest_dir))
            if not os.path.exists(dest_dir):
                self.logger.info("Creating directory:\n\t%s" % (dest_dir))
                os.makedirs(dest_dir)

            #  This should never happen since we clean up after each job...
            if os.path.isfile(upload_file):
                self.logger.info("Upload file already exists!\n\t%s" % (upload_file))
                continue

            #  Link to the location in the gluster hash store
            hex_md5 = startup_lib.convert_base64_to_hex(md5_hash)
            hashstore_path = "%s/accounts/%s/hashstore/%s" % \
                                    (startup_lib.MASTER_MOUNT,
                                     self.account,
                                     hex_md5)
            self.logger.info("linking %s to %s" % (hashstore_path, upload_file))
            os.symlink(hashstore_path, upload_file)

            #  Finally, link the base directory to the fake root
            fake_base = "%s%s" % (self.fake_root, base_dir)
            if not self.docker and not os.path.exists(base_dir):
                self.logger.info("linking %s to %s" % (base_dir, fake_base))
                os.symlink(fake_base, base_dir)
                self.logger.info("Adding %s to list of base dirs" % (base_dir))
            if not base_dir in self.fake_base_dirs:
                self.fake_base_dirs.append(base_dir)

        self.logger.info("Done creating job links")

        return


    def get_houdini_command(self):
        """ setup the houdini command if copying directory """
        command_split = self.command.split(';')
        hou_command = "%s %s" % (command_split[0], self.jid)
        if len(command_split) > 1:
            self.command = "%s;%s" % (hou_command, command_split[1:])
        else:
            self.command = hou_command


    def setup_environment(self):
        """ Setup the needed environment variables to get applications working """
        self.setup_generic_environment()

        self.logger.info("Setting Maya environment variables...")
        setup_maya_env()

        self.logger.info("Setting Katana environment variables...")
        setup_katana_env()

        self.logger.info("Setting Nuke environment variables...")
        setup_nuke_env()

        self.logger.info("Setting Vray license server...")
        self.set_vray_license()


        self.logger.info("Environment setup complete!")
        log_env(self.logger)



    def start_machine(self):
        start_dict = {'name':startup_lib.hostname,
                      'account':self.account,
                      'resource':self.resource,
                      'class':self.metadata['machine_type']}

        url = "%s/api/v1/instance/initmachine" % self.conductor_url
        self.logger.debug("init machine url: %s", url)
        request = urllib2.Request(url)

        base64string = base64.encodestring('%s:%s' % (
            startup_lib.username,
            startup_lib.password)).replace('\n', '')

        request.add_header("Authorization", "Basic %s" % base64string)
        request.add_header('Content-Type', 'application/json')
        request.get_method = lambda: 'POST'

        attempts = 1
        response = None
        data = None
        while attempts < 6:
            try:
                response = urllib2.urlopen(request, json.dumps(start_dict))
                attempts = 7
            except urllib2.HTTPError, excep:
                self.logger.debug("Caught error, %s" % excep)
                time.sleep(attempts)
                attempts += 1
        if response is not None:
            data = json.loads(response.read())
        else:
            self.logger.error("Could not connect to app to init machine! shutting down.")
            self.stop_machine()
        return data


    def stop_machine(self):
        if not self.auto_kill:
            self.logger.info('not killing machine b/c auto_kill is not set')
            return {}

        self.copy_instance_log()
        self.logger.info('killing machine')
        stop_dict = {
            'instance':startup_lib.hostname,
            'account':self.account,
            'resource':self.resource}
        request = urllib2.Request("%s/api/v1/instance/stopmachine" % self.conductor_url)

        base64string = base64.encodestring('%s:%s' % (
            startup_lib.username,
            startup_lib.password)).replace('\n', '')

        request.add_header("Authorization", "Basic %s" % base64string)
        request.add_header('Content-Type', 'application/json')
        request.get_method = lambda: 'PUT'

        attempts = 1
        while attempts < 6:
            try:
                response = urllib2.urlopen(request, json.dumps(stop_dict))
                attempts = 7
            except urllib2.HTTPError, excep:
                self.logger.debug("Caught error, %s" % excep)
                time.sleep(attempts)
                attempts += 1

        data = json.loads(response.read())
        startup_lib.delete_instance(startup_lib.hostname, logger=self.logger)
        return data

    def get_docker_command(self, docker_image, raw_command, output_dirs, environment):
        command = 'gcloud docker run -- --interactive '

        # expose fake_base_dirs to container
        for base_dir in self.fake_base_dirs:
            from_dir = os.path.join(self.fake_root, base_dir.lstrip('/'))  # why does this not work?
            to_dir = os.path.join('/', base_dir)
            self.logger.debug('exposing %s as %s in container', from_dir, to_dir)
            command += ' --volume=%s:%s' % (from_dir, to_dir)

        # expose output dirs to host
        for directory in output_dirs:
            command += ' --volume=%s:%s ' % (directory, directory)

        # expose gluster to docker to make symlinks work
        command += ' --volume=/mnt/cndktr_glus:/mnt/cndktr_glus '

        # set environment variables
        for key, value in environment.iteritems():
            command += ' --env="%s=%s" ' % (key, value)

        command += ' '
        command += os.path.join(DOCKER_REGISTRY, docker_image)
        command += ' '
        command += raw_command

        return command


    def get_command(self):
        """Retrieve the command to run from the next pending job on the queue.
        """
        # pass the app the instance name and the instance resource
        start_dict = {
            'instance':startup_lib.hostname,
            'resource':self.resource,
            'account':self.account}
        next_endpoint = "%s/jobs/next" % self.conductor_url
        self.logger.debug('connecting to %s' % next_endpoint)
        request = urllib2.Request(next_endpoint)

        base64string = base64.encodestring('%s:%s' % (
            startup_lib.username,
            startup_lib.password)).replace('\n', '')

        request.add_header("Authorization", "Basic %s" % base64string)
        request.add_header('Content-Type', 'application/json')
        request.get_method = lambda: 'PUT'

        attempts = 1
        while attempts < 6:
            try:
                response = urllib2.urlopen(request, json.dumps(start_dict))
                attempts = 7
            except urllib2.HTTPError, excep:
                self.logger.debug("Caught error, %s" % excep)
                time.sleep(attempts)
                attempts += 1

        response_data = response.read()
        self.logger.debug('response.code is: \n%s', response.code)
        self.logger.debug('response.code.__class__ is: \n%s', response.code.__class__)
        self.logger.debug('response_data is: \n%s', response_data)

        if response.code == 204:
            self.command = None
            return
        data = json.loads(response_data)

        if 'error' in data.keys():
            return None, None, None
        jid = str(data['body']['jid']).zfill(5)
        tid = str(data['body']['task']['tid']).zfill(3)
        self.logger.info("NOW RUNNING: %s.%s" % (jid, tid))
        try:
            out_dir = str(data['body']['task']['output_dir'])
        except KeyError, excep:
            out_dir = None
            self.logger.warn("Output Dir not returned, %s" % excep)
        try:
            frame = str(data['body']['task']['frame'])
        except KeyError, excep:
            frame = None
            self.logger.warn("Frame not returned, %s" % excep)

        if data['body']['task'].get('environment'):
            try:
                self.custom_environment = data['body']['task']['environment']
                self.logger.info("received env data: %s" % self.custom_environment)
            except KeyError, excep:
                self.custom_environment = None
                self.logger.info("No envir data received")

        self.jid = jid
        self.tid = tid

        if data['body']['task'].get('docker_image'):
            # set docker command
            self.docker = True
            self.delete_log_files()
            self.create_job_links()
            out_dirs = copy.copy(DEFAULT_OUT_DIRS)
            if out_dir:
                out_dirs.append(out_dir)
            self.logger.debug('DEFAULT_OUT_DIRS is: %s', DEFAULT_OUT_DIRS)
            self.logger.debug('out_dirs is: %s', out_dirs)

            self.command = self.get_docker_command(
                data['body']['task']['docker_image'],
                data['body']['task']['command'],
                out_dirs,
                data['body']['task'].get('environment'))

        else:
            #  Set up environment variables if necessary
            self.command = str(data['body']['task']['command'])
            self.delete_log_files()
            #  Set any sym links for this job...
            self.create_job_links()


        self.fix_maya_filename()
        if self.command.startswith('hou-mantra'):
            self.get_houdini_command()


        if "maya2015Render" not in self.command:
            # send all output to /var/log/render_log
            self.command = self.command + " > /var/log/render_log 2>&1"

        self.logger.debug('command is %s', self.command)

        if out_dir:
            self.out_dirs.append(out_dir)
        self.frame = frame

    def verify_task(self):
        """ Make sure this instance is the instance listed as running this task """
        attempts = 1
        while attempts < 6:
            try:
                request = urllib2.Request("%s/jobs/%s/%s" % (
                    self.conductor_url,
                    self.jid, self.tid))
                base64string = base64.encodestring('%s:%s' % (
                    startup_lib.username,
                    startup_lib.password)).replace('\n', '')
                request.add_header("Authorization", "Basic %s" % base64string)
                request.add_header('Content-Type', 'application/json')
                request.get_method = lambda: 'GET'
                response = urllib2.urlopen(request)
                data = json.loads(response.read())
                instance = data['task']['instance']
                if instance != startup_lib.hostname and str(instance) != "None":
                    self.logger.info("job instance %s is not the same as host instance %s" % (instance, startup_lib.hostname))
                    self.logger.info("job is running on another box!")
                    attempts = 7
                    return False
                else:
                    attempts = 7
                    return True
            except Exception, excep:
                self.logger.warn("Failed to verify task with conductor app: %s" % excep)
                attempts += 1
                time.sleep(5)

        self.logger.error("Failed to verify task with conductor app2222: %s" % excep)
        return False


    def get_and_verify_job(self):
        """ Get the job command information and verify
        that datastore registered this machine with the job """
        attempts = 1
        self.jid = None
        self.tid = None
        self.command = None
        self.out_dirs = copy.copy(DEFAULT_OUT_DIRS)
        self.frame = None
        self.docker = False
        while attempts < 6:
            try:
                self.get_command()
                attempts = 7
            except Exception, excep:
                self.logger.error('hit exception:')
                self.logger.error(excep)
                self.logger.error(traceback.format_exc())
                attempts += 1
                time.sleep(4)
                self.logger.info("Failed to get a command to run, trying again %s" % excep)

        if self.jid is None:
            return

        time.sleep(random.randint(5, 10))

        if not self.verify_task():
            self.get_and_verify_job()
        else:
            return


    def get_job_command(self):
        """ Retrieve a task to run from conductor """
        attempt = 1
        while attempt < 6:
            try:
                self.get_and_verify_job()
                attempt = 7
            except Exception, excep:
                self.logger.error("Failed to get job command! \n%s" % traceback.format_exc())
                self.logger.info(excep)
                attempt += 1
                time.sleep(5)


    def delete_log_files(self):
        """ Clean up any old logs """

        # If the katana log exists, delete it
        if os.path.lexists('/tmp/katana.log'):
            os.remove('/tmp/katana.log')

        # If the render log exists, delete it
        if os.path.lexists('/var/log/render_log'):
            os.remove('/var/log/render_log')

        self.logger.info("Cleaning base directory links...")
        #  Clean out any base directory links
        for base_dir in self.fake_base_dirs:
            if os.path.exists(base_dir):
                self.logger.info("Removing base directory link %s" % (base_dir))
                if os.path.islink(base_dir):
                    os.remove(base_dir)
                else:
                    shutil.rmtree(base_dir)

        self.logger.info("Removing the fake root...")
        #  Now remove the fake root...
        if os.path.exists(self.fake_root):
            self.logger.info("Removing fake root %s" % (self.fake_root))
            shutil.rmtree(self.fake_root)
        self.logger.info("Done cleaning up!")


    def copy_final_log(self, out, err, returncode):
        """ After the work is complete, copy the log over. """
        self.logger.debug("STDOUT: %s" % out)
        self.logger.debug("STDERR: %s" % err)
        self.logger.debug("RETURNCODE: %s" % returncode)
        log_copy_cmd = 'gsutil cp /var/log/render_log'\
            ' gs://%s/%s/render_scripts/logs/maya/%s.%s.log' % (startup_lib.DEFAULT_BUCKET, self.account, self.jid, self.tid)
        proc = subprocess.Popen(log_copy_cmd, shell=True)
        proc.communicate()
        return proc.returncode


    def copy_instance_log(self):
        """ Transfer instance logs to GCS. """
        log_filepath = os.environ.get("CONDUCTOR_LOG")
        gcs_path = os.path.join(
            'gs://',
            startup_lib.DEFAULT_BUCKET,
            'instance_logs',
            startup_lib.hostname
        )
        log_copy_cmd = 'gsutil cp %s %s' % (log_filepath, gcs_path)
        proc = subprocess.Popen(log_copy_cmd, shell=True)
        proc.communicate()
        return proc.returncode


    def run_command(self):
        """ run the provided command returning the return code """
        proc = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            env=self.job_environment)
        out, err = proc.communicate()
        returncode = proc.returncode
        self.copy_final_log(out, err, returncode)
        return returncode


    def copy_images(self, copy_cmd):
        """ Copy images to cloud storage """
        returncode = 1
        tries = 0
        while returncode != 0 and tries < 6:
            time.sleep(tries * 10)
            self.logger.info("Running command: %s" % copy_cmd)
            tries += 1
            proc = subprocess.Popen(
                copy_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = proc.communicate()
            returncode = proc.returncode
            self.logger.info(stdout)
            self.logger.info(stderr)
        if tries > 5:
            self.logger.error("Failed to copy files!")
            raise IOError("Failed to copy rendered image!")

    def get_rendered_images(self):
        """ Given the list of output directories, look for any rendered images.
            Call self.copy_images to transfer rendered images.
            Return a list of (path: md5) tuples
        """
        self.logger.info("DIRLIST: %s" % self.out_dirs)
        return_values = []
        # Ugly directory walking
        for image_dir in self.out_dirs:
            for dir_list in os.walk(image_dir):
                for i in dir_list[2]:
                    subdir = dir_list[0].split(image_dir)[-1]
                    image_file = dir_list[0] + '/' + i
                    if image_file.endswith('.tmp'):
                        continue
                    if self.frame is not None:
                        if self.frame not in image_file:
                            continue
                    # Once we're running houdini sims
                    # this will need to be removed
                    if image_file.endswith('.ifd'):
                        continue

                    image_copy_cmd = 'gsutil cp -r %s gs://%s/accounts/%s/output_render/'\
                        '%s/' % (image_file, startup_lib.DEFAULT_BUCKET, self.account, self.jid)
                    if subdir:
                        if subdir.startswith('/'):
                            subdir = "/".join(subdir.split('/')[1:])
                        image_copy_cmd += "%s/" % subdir

                    self.copy_images(image_copy_cmd)
                    image_md5 = startup_lib.generate_md5(image_file)
                    return_values.append((str(image_file),image_md5))
        return return_values

    def set_complete(self, rendered_images=[]):
        """ Alert the app that the work is complete. """
        request_dict = { 'status': self.status, 'rendered_images': rendered_images }
        finish_endpoint = "%s/jobs/%s/%s/finish" % (self.conductor_url, self.jid, self.tid)
        self.logger.debug('connecting to endpoint %s' % finish_endpoint)
        request = urllib2.Request(finish_endpoint)
        base64string = base64.encodestring('%s:%s' % (
            startup_lib.username,
            startup_lib.password)).replace('\n', '')
        request.add_header("Authorization", "Basic %s" % base64string)
        request.add_header('Content-Type', 'application/json')
        request.get_method = lambda: 'PUT'
        attempts = 1

        while attempts < 10:
            try:
                response = urllib2.urlopen(request, json.dumps(request_dict))
            except urllib2.HTTPError, excep:
                self.logger.debug("caught error %s" % excep)
                response = None

            if response is not None:
                data = json.loads(response.read())
                if "status" in data.keys() and data['status'] == '201':
                    attempts = 11

            if attempts < 10:
                time.sleep(2 * attempts)



            attempts += 1

        self.logger.debug("Exiting set_complete.  attempts=%s", attempts)
        return data

    def fix_maya_filename(self):
        if "maya2015Render" in self.command:
            maya_file = " ".join(self.command.split(' -rl ')[-1].split()[1:])
            command = self.command.split(maya_file)[0]
            root = maya_file.split('/')[0]
            if len(root) == 2 and root[1] == ":":
                letter = root[0]
                new_root = '/mnt/cndktr_glus/windows_%s' % letter
                maya_file = maya_file.replace(root, new_root)
            maya_file = "'%s'" % maya_file
            new_command = "%s %s" % (command, maya_file)
            self.logger.info('changing command to: %s', new_command)
            self.command = new_command


    #  Figure out the job environment based on any custom settings
    def get_job_environment(self):
        self.logger.info("Setting up job environment %s" % self.custom_environment)
        env_command = "env"
        if self.custom_environment:
            self.logger.info("Adding custom environment settings...")
            for key, value in self.custom_environment.iteritems():
                self.logger.info("adding %s=%s" % (key, value))
                env_command = 'export %s="%s" && %s' % (key, value, env_command)

        self.logger.info("Getting modified environment with %s" % env_command)
        output = subprocess.check_output(env_command, stderr=subprocess.PIPE, shell=True)
        env_lines = sorted(output.splitlines(False))

        self.logger.info("new environment is %s" % env_lines)
        self.job_environment = {}
        envir_log = "/var/log/envir_log"
        envir_file = open(envir_log, "w")
        for line in env_lines:
            envir_file.write("%s\n" % line)
            env_setting = line.split('=')
            if len(env_setting) == 2:
                self.job_environment[env_setting[0]] = env_setting[1]
        self.logger.info("Done writing to environment log %s" % envir_log)
        envir_file.close()

        #  Write out the environment to a place where it can be viewed
        #  by the end user
        log_copy_cmd = 'gsutil cp /var/log/envir_log'\
            ' gs://%s/%s/render_scripts/logs/envir/%s.%s.log' % \
            (startup_lib.DEFAULT_BUCKET, self.account, self.jid, self.tid)
        self.logger.info("Copying envir log with %s" % log_copy_cmd)
        proc = subprocess.Popen(log_copy_cmd, shell=True)
        proc.communicate()

    def run_render_loop(self):
        '''
        Running loop that is asking the app for work and operating on that work

        In Regards to log files:
            1. Delete render_log and katana.log from disk
            2. If the job is katana job symlink katana.log as render_log
               (which neither files exist at this point)
            3. Start the startup_lib.Log thread (which would create render_log if
               it didn't already exist)
        '''
        while self.running:
            self.status = "success"
            self.logger.info("Starting Render...")
            self.get_job_command()
            if self.command is not None:
                self.delete_log_files()
                # self.fix_maya_filename()

                # If the command is a houdin command then hack it.  Why not?
                # if self.command.startswith('hou-mantra'):
                #     self.get_houdini_command()

                # If the command is a katana command then use the katana log as the render_log
                if ".katana" in self.command:
                    os.symlink('/tmp/katana.log', '/var/log/render_log')

                # Start the log copier thread
                log_thread = startup_lib.Log(self.account, self.jid, self.tid)
                log_thread.start()

                self.logger.info("Executing command: %s", self.command)

                #  Set up job environment with any custom settings
                self.get_job_environment()

                #  Set any sym links for this job...
                self.create_job_links()

                returncode = self.run_command()
                if returncode != 0:
                    self.status = "failed"
                rendered_images = self.get_rendered_images()
                self.set_complete(rendered_images)
                log_thread.signal = False
                time.sleep(1)
                self.logger.info("Completed Task - %s %s" % (self.jid, self.tid))
            else:
                now = time.time()
                uptime = now - self.starttime
                self.logger.info("No work found, current uptime is %s" % uptime)
                if uptime > self.min_running_time:
                    self.logger.info("shutting down host in 10 seconds")
                    time.sleep(10)
                    self.running = False
                    # Shut down the instance.
                    self.stop_machine()
                else:
                    time.sleep(30)


    def main(self):
        """ Main application entry """
        self.start_machine()  # Register this machine with the App
        self.setup_environment()  # Setup the generic env and mount gluster
        self.run_render_loop()  # Run the main render loop
        self.logger.info('would be exiting main and stopping machine')
        self.stop_machine()  # If by chance we exit the loop, shut it down.



if __name__ == "__main__":

    # Attempt to setup logging first so that we can record any issues immediately for debugging
    try:
        log_filepath = startup_lib.get_conductor_log_path(strict=True)
        logger = startup_lib.setup_logging(log_filepath)
    except:
        startup_lib.print_stderr('Failed to initialize logger')
        startup_lib.print_last_exception()
        raise

    # Start the render loop
    try:
        render = Render(logger)
        render.main()
    except:
        startup_lib.print_last_exception(logger)
        # Global fail safe to kill instance
        try:
            render.stop_machine()
        except:
            logger.debug('would be deleting instance')
            startup_lib.print_last_exception(logger)
            startup_lib.delete_instance(startup_lib.hostname, logger=logger)
    finally:
        if os.environ.get('AUTO_KILL'):
            logger.info("shutting down")
            subprocess.call(['shutdown', '-h', 'now'])
