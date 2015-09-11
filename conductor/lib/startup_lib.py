

"""
Library for providing stable environment for running startup scripts on gce instances.
"""

import binascii
import os
import subprocess
import threading
import httplib2
import urllib2
import base64
import json
import time
import socket
import sys
import traceback
import logging
import hashlib

MASTER_MOUNT = "/mnt/cndktr_glus"
hostname = socket.gethostname()

# these are set in startup.sh
INTERNAL_ACCOUNT_URL = os.environ['INTERNAL_ACCOUNT_URL']
BASE_URL = os.environ['BASE_URL']
DEFAULT_BUCKET = os.environ['DEFAULT_BUCKET']
username = os.environ['USERNAME']
password = os.environ['PASSWORD']


def convert_base64_to_hex(string):
    binary = binascii.a2b_base64(string)
    hex = binascii.b2a_hex(binary)
    return hex


def get_conductor_log_path(strict=True):
    '''
    Return the value of the the CONDUCTOR_LOG environment variable.
    If strict and the variable does not exist or it has an empty value, raise
    an exception
    '''
    log_filepath = os.environ.get("CONDUCTOR_LOG")
    if not log_filepath and strict:
        msg = "Expected variable CONDUCTOR_LOG not set"
        raise Exception(msg)
    return log_filepath


def print_stderr(string):
    '''
    Print the given string to stderr and flush the stream buffer immediately.
    WARNING: This call should be used sparingly, and especially avoided when
    running in large loops. Typically a python logger object would be the better
    solution for printing.
    '''
    sys.stderr.write(string)
    sys.stderr.flush()

def print_last_exception(logger=None):
    '''
    Print the last exception in the stack to the given logger object.  If no
    logger object is given print to stderr
    '''
    stack_lines = traceback.format_exception(*sys.exc_info())
    header = stack_lines[-1]
    stack_str = "".join(stack_lines)
    msg = ('\n###############################################\n'
           'EXCEPTION CAUGHT: %s'
           '###############################################\n'
           '%s'
           '###############################################\n' % (header, stack_str))
    if logger:
        logger.info(msg)
    else:
        print_stderr(msg)


def setup_logging(log_filepath):
    '''
    Create a logging object using the given log_filepath
    '''
    logger = logging.getLogger('render_node')
    logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(log_filepath)
    file_handler.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s - %(levelname)8s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

def copy_instance_log(logger_file=None):
    """ Copy the instance log to cloud storage """
    if logger_file is None:
        logger_file = get_conductor_log_path(strict=True)
    log_copy_cmd = 'gsutil cp %s gs://%s/instance_logs/' % (DEFAULT_BUCKET, logger_file)
    subprocess.call(log_copy_cmd, shell=True)


def delete_instance(instance_name, instance_zone="us-central1-f", logger=None):
    def log(msg=''):
        if logger:
            logger.debug(msg)
        else:
            print msg

    if not os.environ.get('AUTO_KILL'):
        log('not killing instance')
        return
    log('killing instance')
    """ Delete the instance using the gcloud api """
    delete_cmd = "/usr/local/bin/gcloud compute instances delete --delete-disks all --zone %s -q %s" % (
        instance_zone,
        instance_name)
    proc = subprocess.Popen(delete_cmd, shell=True)
    proc.communicate()
    returncode = proc.returncode
    if returncode != 0:
        log("Failed to kill instance! Forcing...")
        subprocess.call(['shutdown', '-h', 'now'])
    else:
        log('completed termination request')

def get_metadata(logger=None):
    """ Get the metadata associated with this instance """
    http = httplib2.Http()
    response, content = http.request(
        'http://metadata.google.internal/computeMetadata/'\
        'v1/instance/attributes/?recursive=True',
        headers={'Metadata-Flavor': 'Google'})
    metadata = eval(content)
    if logger:
        logger.debug("response: %s" % response)
    return metadata

def get_metadata_attribute(attribute, logger=None, metadata=None):
    """ Return the account name for this instance """
    if metadata is None:
        metadata = get_metadata(logger)
    attributeValue = metadata.get(attribute, None)
    return attributeValue

def generate_md5(filepath, blocksize=65536):
    '''
    Generate and return md5 hash (base64) for the given filepath
    '''
    hash_obj = hashlib.md5()
    file_obj = open(filepath, 'rb')
    file_buffer = file_obj.read(blocksize)
    while len(file_buffer) > 0:
        hash_obj.update(file_buffer)
        file_buffer = file_obj.read(blocksize)
    return  base64.b64encode(hash_obj.digest())


class Log(threading.Thread):
    """ Seperate thread to upload log files to cloud storage """
    def __init__(self, account, jid, tid):
        threading.Thread.__init__(self)
        self.signal = True
        self.account = account
        self.jid = jid
        self.tid = tid
        self.metadata = get_metadata()

    def run(self):

        """ Logging run thread """
        while self.signal:
            if not os.path.exists('/var/log/render_log'):
                job_text = 'STARTING JOB...\n'
                logfile = open('/var/log/render_log', 'w')
                logfile.write(job_text)
                logfile.flush()
                logfile.close()
            log_copy_cmd = 'cp /var/log/render_log /tmp/upload_log;'\
                'gsutil cp /tmp/upload_log gs://%s/%s/render_scripts/logs/maya/%s.%s.log' % (
                    DEFAULT_BUCKET, self.account,
                    self.jid, self.tid)
            subprocess.call(log_copy_cmd, shell=True)
            time.sleep(15)


class StartupScript(object):
    """
    Base class for startscripts running on GCE.
    This will get the appropriate account information and mount the gluster filesystem
    associated with the instance running.
    """
    def __init__(self, logger):
        self.logger = logger
        self.metadata = get_metadata(logger)
        self.account = get_metadata_attribute("account", logger, self.metadata)
        self.tags = self.get_tags()
        self.mounts = None
        self.project = get_metadata_attribute("project", logger, self.metadata)
        self.create_home_dir()
        self.mounted = self.mount_gluster()
        self.auto_kill = True if os.environ.get('AUTO_KILL') else False
        if os.environ.get('CONDUCTOR_DEVELOPMENT'):
            self.conductor_url = "http://%s-dot-%s" % (self.account, BASE_URL)
        else:
            self.conductor_url = "https://%s-dot-%s" % (self.account, BASE_URL)


    def get_tags(self):
        """ Get the tags for this instance """
        http = httplib2.Http()
        response, content = http.request(
            'http://metadata.google.internal/computeMetadata/v1/instance/tags',
            headers={'Metadata-Flavor': 'Google'})
        tags = eval(content)
        self.logger.debug("response: %s" % response)
        return tags

    def setup_generic_environment(self):
        """ Run processes to setup the render environment """
        os.chdir('/home/conductor')
        subprocess.call('chmod 777 /Volumes', shell=True)
        subprocess.call('chmod 777 %s' % MASTER_MOUNT, shell=True)
        self.logger.info("Creating Symbolic Links at mount points...")
        os.environ['CONDUCTOR_MOUNT'] = MASTER_MOUNT


    def create_home_dir(self):
        """ Create a home directory to use """
        self.logger.debug("Creating conductor user home dir.")
        if not os.path.exists("/home/conductor"):
            os.makedirs('/home/conductor')
        os.environ['HOME'] = '/home/conductor'


    def get_mount_points(self):
        """ Get the mount list from the application """
        self.logger.debug('getting mount points for account')
        request = urllib2.Request("%s/api/v1/account/mounts" % self.conductor_url)
        base64string = base64.encodestring(
            '%s:%s' % (username, password)).replace('\n', '')
        request.add_header("Authorization", "Basic %s" % base64string)
        request.add_header('Content-Type', 'application/json')
        request.get_method = lambda: 'GET'
        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError, e:
            return None
        data = json.loads(response.read())
        self.logger.debug('data is: %s', data)
        self.mount_points = data['data']['mounts']
        if data['data']['mounts']:
            return data['data']['mounts']
        return None


    # TODO(mkr): why do we do this?
    def send_mount_points(self):
        self.logger.debug('sending mount points')
        mount_dict = {'mounts': self.mount_points}
        request = urllib2.Request("%s/api/v1/account/mounts" % self.conductor_url)
        base64string = base64.encodestring(
            '%s:%s' % (username, password)).replace('\n', '')
        request.add_header("Authorization", "Basic %s" % base64string)
        request.add_header('Content-Type', 'application/json')
        request.get_method = lambda: 'POST'
        try:
            response = urllib2.urlopen(request, json.dumps(mount_dict))
        except urllib2.HTTPError, e:
            return None
        data = json.loads(response.read())
        if data['status'] != "200":
            self.logger.error("Could not set mount points! Check server logs!")
            raise RuntimeError("Could not set mount points! Check server logs!")
        self.logger.debug('mount points sent')


    def create_mount_links(self):
        for mount_name in self.mount_points:
            src_link = os.path.join(MASTER_MOUNT, mount_name)
            dest_link = "/%s" % mount_name
            if not os.path.exists(dest_link):
                try:
                    os.symlink(src_link, dest_link)
                except OSError, e:
                    pass
            dest_link = mount_name
            if not os.path.exists(dest_link):
                try:
                    os.symlink(src_link, dest_link)
                except OSError, e:
                    pass
            # create non-letter mapped links
            if ":" in mount_name:
                letter = mount_name[0]
                dest_link = "/mnt/cndktr_glus/windows_%s" % letter.upper()
                if not os.path.exists(dest_link):
                    try:
                        os.symlink(src_link, dest_link)
                    except OSError, e:
                        pass
                dest_link = "/mnt/cndktr_glus/windows_%s" % letter.lower()
                if not os.path.exists(dest_link):
                    try:
                        os.symlink(src_link, dest_link)
                    except OSError, e:
                        pass


    def create_mount_dir(self):
        if not os.path.exists(MASTER_MOUNT):
            os.makedirs(MASTER_MOUNT)
            os.chmod(MASTER_MOUNT, 0777)

    def mount_gluster(self):
        """ mount the gluster file system for this account """
        self.logger.debug("Creating the mount directory")
        self.create_mount_dir()
        self.logger.debug("Attempting to mount drive...")
        tries = 1
        glus_server = "%s-glus-000-00" % self.account
        mounted = False

        while tries < 6:
            result = subprocess.call(
                '/sbin/mount.glusterfs %s:/af0 %s' % (glus_server, MASTER_MOUNT),
                shell=True)
            if result == 0:
                self.logger.debug("Mounted gluster drive.")
                mounted = True
                tries = 6
            else:
                tries += 1
                self.logger.debug(
                    "Failed to mount gluster drive, sleeping for %s seconds" % (10 * tries))
                time.sleep(10 * tries)
        if not mounted:
            # kill machine
            self.logger.error("Could not mount gluster, stopping instance")
            delete_instance(hostname, logger=self.logger)
        if self.verify_filesystem() != 0:
            self.logger.error(
                "Could not list file system! Problem with the file system! Shutting down.")
            delete_instance(hostname, logger=self.logger)
        return mounted

    def verify_filesystem(self, sleeper=5):
        return 0
        """ list the contents of the mount to make sure it's responsive """
        self.logger.debug("Making sure the file system is alive.")
        result = subprocess.call('ls -l %s' % MASTER_MOUNT, shell=True)
        time.sleep(sleeper)
        return result
