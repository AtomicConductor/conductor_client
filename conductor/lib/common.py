import hashlib
import logging
import math
import multiprocessing
import os
import platform
import signal
import subprocess
import time
import traceback
import base64
import yaml

def setup_logger():
    """ This function is called when this file is imported!
    Returns a general formatted logging object.
    """
    logger = logging.getLogger("ConductorClient")
    if os.environ.has_key('CONDUCTOR_DEVELOPMENT'):
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(levelname)s - %(lineno)d - %(filename)s.%(funcName)s\n    %(message)s')
    else:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s -  %(message)s',
            "%Y-%m-%d %H:%M:%S")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


# Global logger object, don't use this object directly.
# It is preferred to use the conductor.logger in the conductor __init__.py
# except within this file
LOGGER = setup_logger()


# Create trap for SIGINT that sets common.EXIT to true
SIGINT_EXIT = False
def signal_handler(sig_number,stack_frame):
    LOGGER.debug('in signal_handler. setting common.SIGINT_EXIT to True')
    global SIGINT_EXIT
    SIGINT_EXIT = True
signal.signal(signal.SIGINT, signal_handler)

def register_sigint_signal_handler(signal_handler=signal_handler):
    signal.signal(signal.SIGINT, signal_handler)


# ##
# Global Functions
# ##


def on_windows():
    '''
    Return True if the current system is a Windows platform
    '''
    return platform.system() == "Windows"


def retry(function, retry_count=5):
    def check_for_early_release(error):
        LOGGER.debug('checking for early_release. EXIT is %s' % EXIT)
        if EXIT:
            LOGGER.debug('releasing in retry')
            raise error

    # disable retries in testing
    if os.environ.get('FLASK_CONF') == 'TEST':
        retry_count = 0

    i = 0
    while True:
        try:
            LOGGER.debug('trying to run %s' % function)
            return_values = function()
        except Exception, e:
            LOGGER.debug('caught error')
            LOGGER.debug('failed due to: \n%s' % traceback.format_exc())
            if i < retry_count:
                check_for_early_release(e)
                sleep_time = int(math.pow(2, i))
                LOGGER.debug('retrying after %s seconds' % sleep_time)
                time.sleep(sleep_time)
                i += 1
                check_for_early_release(e)
                continue
            else:
                LOGGER.debug('exceeded %s retries. throwing error...' % retry_count)
                raise e
        else:
            LOGGER.debug('ran %s ok' % function)
            return return_values

def run(cmd):
    LOGGER.debug("about to run command: " + cmd)
    command = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = command.communicate()
    status = command.returncode
    return status, stdout, stderr

def get_md5(file_path, blocksize=65536):
    hasher = hashlib.md5()
    afile = open(file_path, 'rb')
    buf = afile.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(blocksize)
    return hasher.digest()

def get_base64_md5(*args, **kwargs):
    md5 = get_md5(*args)
    b64 = base64.b64encode(md5)
    return b64


class Config():
    required_keys = ['account']
    default_config = {
        # TODO
        'base_url': 'atomic-light-001.appspot.com',
        'thread_count': (multiprocessing.cpu_count() * 2),
        'instance_cores': 16,
        'resource': 'default',
        'priority': 5,
        'local_upload': True,
    }


    def __init__(self):
        LOGGER.debug('base dir is %s' % self.base_dir())

        # create config. precedence is ENV, CLI, default
        combined_config     = self.default_config
        combined_config.update(self.get_user_config())
        combined_config.update(self.get_environment_config())

        # verify that we have the required params
        self.verify_required_params(combined_config)

        # set the url based on account (unless one was already provided)
        if not 'url' in combined_config:
            combined_config['url'] = 'https://%s-dot-%s' % (combined_config['account'],
                                                            combined_config['base_url'])

        self.validate_client_token(combined_config)
        self.config = combined_config
        LOGGER.debug('config is:\n%s' % self.config)


    def validate_client_token(self,config):
        """
        load conductor config. default to base_dir/auth/CONDUCTOR_TOKEN.pem
        if token_path is not specified in config
        """
        if not 'token_path' in config:
            config['token_path'] = os.path.join(self.base_dir(),'auth/CONDUCTOR_TOKEN.pem')
        token_path = config['token_path']
        try:
            with open(token_path,'r') as f:
                conductor_token = f.read().rstrip()
        except IOError, e:
            message = 'could not open client token file in %s\n' % token_path
            message += 'either insert one there, set token_path to a valid token,\n'
            message += 'or set the CONDUCTOR_TOKEN_PATH env variable to point to a valid token\n'
            message += 'refusing to continue'
            LOGGER.error(message)
            raise ValueError(message)
        config['conductor_token'] = conductor_token


    def base_dir(self):
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


    # look for any environment settings that start with CONDUCTOR_
    def get_environment_config(self):
        environment_config = {}
        for env in os.environ:
            if env.startswith('CONDUCTOR_'):
                # skip these options
                if env in ['CONDUCTOR_DEVELOPMENT','CONDUCTOR_CONFIG']:
                    continue
                # if we find a match, strip the conductor_ prefix and downcase it
                config_name = env[10:].lower()
                environment_config[config_name] = os.environ[env]

        return environment_config

    def get_config_file_path(self, config_file=None):
        default_config_file = os.path.join(self.base_dir(), 'config.yml')
        if os.environ.has_key('CONDUCTOR_CONFIG'):
            config_file = os.environ['CONDUCTOR_CONFIG']
        else:
            config_file = default_config_file

        return config_file

    def get_user_config(self):
        config_file = self.get_config_file_path()
        LOGGER.debug('using config: %s' % config_file)


        if os.path.isfile(config_file):
            LOGGER.debug('loadinf config from: %s', config_file)
            try:
                with open(config_file, 'r') as file:
                    config = yaml.load(file)
            except IOError, e:
                message = "could't open config file: %s\n" % config_file
                message += 'please either create one or set the CONDUCTOR_CONFIG\n'
                message += 'environment variable to a valid config file\n'
                message += 'see %s for an example' % os.path.join(self.base_dir(), 'config.example.yml')
                LOGGER.error(message)

                raise ValueError(message)
        else:
            LOGGER.warn('config file %s does not exist', config_file)
            return {}


        if config.__class__.__name__ != 'dict':
            message = 'config found at %s is not in proper yaml syntax' % config_file
            LOGGER.error(message)
            raise ValueError(message)

        LOGGER.debug('config is %s' % config)
        LOGGER.debug('config.__class__ is %s' % config.__class__)
        return config

    def verify_required_params(self, config):
        LOGGER.debug('config is %s' % config)
        for required_key in self.required_keys:
            if not required_key in config:
                message = "required param '%s' is not set in the config\n" % required_key
                message += "please either set it or export CONDUCTOR_%s to the proper value" % required_key.upper()
                LOGGER.error(message)
                raise ValueError(message)
class Auth:
    pass
