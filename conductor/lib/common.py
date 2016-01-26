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
from functools import wraps

logger = logging.getLogger(__name__)

# Use this global variable across all modules to query whether the the SIGINT signal has been triggered
SIGINT_EXIT = False
def signal_handler(sig_number, stack_frame):
    logger.debug('in signal_handler. setting common.SIGINT_EXIT to True')
    global SIGINT_EXIT
    SIGINT_EXIT = True

def register_sigint_signal_handler(signal_handler=signal_handler):
    logger.debug("REGISTERING SIGNAL HANDLER")
    signal.signal(signal.SIGINT, signal_handler)


def on_windows():
    '''
    Return True if the current system is a Windows platform
    '''
    return platform.system() == "Windows"


def retry(function, retry_count=5):
    def check_for_early_release(error):
        logger.debug('checking for early_release. SIGINT_EXIT is %s' % SIGINT_EXIT)
        if SIGINT_EXIT:
            logger.debug('releasing in retry')
            raise error

    # disable retries in testing
    if os.environ.get('FLASK_CONF') == 'TEST':
        retry_count = 0

    i = 0
    while True:
        try:
            # logger.debug('trying to run %s' % function)
            return_values = function()
        except Exception, e:
            logger.debug('caught error')
            logger.debug('failed due to: \n%s' % traceback.format_exc())
            if i < retry_count:
                check_for_early_release(e)
                # exponential backoff with 250ms base
                sleep_time_in_ms = 250 * int(math.pow(2, i))
                sleep_time = sleep_time_in_ms / 1000.0
                logger.debug('retrying after %s seconds' % sleep_time)
                time.sleep(sleep_time)
                i += 1
                check_for_early_release(e)
                continue
            else:
                logger.debug('exceeded %s retries. throwing error...' % retry_count)
                raise e
        else:
            # logger.debug('ran %s ok' % function)
            return return_values



def dec_timer_exit(func):
    '''
    '''
    @wraps(func)
    def wrapper(*a, **kw):
        func_name = getattr(func, "__name__", "<Unknown function>")
        start_time = time.time()
        result = func(*a, **kw)
        finish_time = '%s :%.2f seconds' % (func_name, time.time() - start_time)
        logger.info(finish_time)
        return result
    return wrapper

def run(cmd):
    logger.debug("about to run command: " + cmd)
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
    if not os.path.isfile(args[0]):
        return None
    md5 = get_md5(*args)
    b64 = base64.b64encode(md5)
    return b64

def generate_md5(filepath, base_64=False, blocksize=65536, poll_seconds=None, state=None):
    '''
    Generate and return md5 hash (base64) for the given filepath
    
    poll_seconds: int, the number of seconds to wait between logging out to the 
                   console when md5 hashing (particularly a large file which
                   may take a while)
    '''
    file_size = os.path.getsize(filepath)
    hash_obj = hashlib.md5()
    file_obj = open(filepath, 'rb')
    buffer_count = 1
    last_time = time.time()
    file_buffer = file_obj.read(blocksize)
    while len(file_buffer) > 0:
        hash_obj.update(file_buffer)
        file_buffer = file_obj.read(blocksize)
        curtime = time.time()
        progress = int(((buffer_count * blocksize) / float(file_size)) * 100)
        if poll_seconds and curtime - last_time >= poll_seconds:
            logger.debug("MD5 hashing %s%% (size %s bytes): %s ", progress, file_size, filepath)
            last_time = curtime

        if state:
            state.hash_progress = progress

        buffer_count += 1

    md5 = hash_obj.digest()

    logger.debug("MD5 hashing 100%% (size %s bytes): %s ", file_size, filepath)
    if base_64:
        return base64.b64encode(md5)
    return md5


def base_dir():
    '''
    Return the top level directory for the local Conductor repo. This is derived
    by traversing up directories from this current script.

    Note that due to symkinks, we can't use os.path.realpath on __file__ because
    __file__ may be a symlinked path and would return the directory for the
    "real" file (as opposed to the directory of the symlinked file (__file__))
    '''
    module_filepath = __file__
    if module_filepath.startswith(".%s" % os.sep):
        # the module filepath will somtimes be relative (to the current working directory), reconstruct full path if necessary
        module_filepath = module_filepath.replace(".%s" % os.sep,
                                                  "%s%s" % (os.getcwd(), os.sep))

    return os.path.dirname(os.path.dirname(os.path.dirname(module_filepath)))

class Config():
    required_keys = ['account']
    default_config = {'base_url': 'atomic-light-001.appspot.com',
                      'thread_count': (multiprocessing.cpu_count() * 2),
                      'instance_cores': 16,
                      'instance_flavor': "standard",
                      'resource': 'default',
                      'priority': 5,
                      'local_upload': True,
                      'md5_caching': True,
                      'log_level': "INFO"}


    def __init__(self):
        logger.debug('base dir is %s' % base_dir())

        # create config. precedence is ENV, CLI, default
        combined_config = self.default_config
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
        logger.debug('config is:\n%s' % self.config)


    def validate_client_token(self, config):
        """
        load conductor config. default to base_dir/auth/CONDUCTOR_TOKEN
        if token_path is not specified in config
        """
        if not 'token_path' in config:
            config['token_path'] = os.path.join(base_dir(), 'auth/CONDUCTOR_TOKEN')
        token_path = config['token_path']
        try:
            with open(token_path, 'r') as f:
                conductor_token = f.read().rstrip()
        except IOError, e:
            message = 'could not open client token file in %s\n' % token_path
            message += 'either insert one there, set token_path to a valid token,\n'
            message += 'or set the CONDUCTOR_TOKEN_PATH env variable to point to a valid token\n'
            message += 'refusing to continue'
            logger.error(message)
            raise ValueError(message)
        config['conductor_token'] = conductor_token





    def get_environment_config(self):
        '''
        Look for any environment settings that start with CONDUCTOR_
        Cast any variables to bools if necessary
        '''
        prefix = 'CONDUCTOR_'
        skipped_variables = ['CONDUCTOR_CONFIG']
        environment_config = {}
        for var_name, var_value in os.environ.iteritems():
            # skip these options
            if not var_name.startswith(prefix) or var_name in skipped_variables:
                continue

            config_key_name = var_name[len(prefix):].lower()
            environment_config[config_key_name] = self._process_var_value(var_value)

        return environment_config

    def _process_var_value(self, env_var):
        '''
        Read the given value (which was read from an environment variable, and
        process it onto an appropriate value for the config.yml file.
        1. cast bool strings into actual python bools
        2. anything else... ?
        '''
        bool_values = {"true": True,
                       "false": False}

        return bool_values.get(env_var.lower(), env_var)


    def get_config_file_path(self, config_file=None):
        default_config_file = os.path.join(base_dir(), 'config.yml')
        if os.environ.has_key('CONDUCTOR_CONFIG'):
            config_file = os.environ['CONDUCTOR_CONFIG']
        else:
            config_file = default_config_file

        return config_file

    def get_user_config(self):
        config_file = self.get_config_file_path()
        logger.debug('using config: %s' % config_file)


        if os.path.isfile(config_file):
            logger.debug('loadinf config from: %s', config_file)
            try:
                with open(config_file, 'r') as file:
                    config = yaml.load(file)
            except IOError, e:
                message = "could't open config file: %s\n" % config_file
                message += 'please either create one or set the CONDUCTOR_CONFIG\n'
                message += 'environment variable to a valid config file\n'
                message += 'see %s for an example' % os.path.join(base_dir(), 'config.example.yml')
                logger.error(message)

                raise ValueError(message)
        else:
            logger.warn('config file %s does not exist', config_file)
            return {}


        if config.__class__.__name__ != 'dict':
            message = 'config found at %s is not in proper yaml syntax' % config_file
            logger.error(message)
            raise ValueError(message)

        logger.debug('config is %s' % config)
        logger.debug('config.__class__ is %s' % config.__class__)
        return config

    def verify_required_params(self, config):
        logger.debug('config is %s' % config)
        for required_key in self.required_keys:
            if not required_key in config:
                message = "required param '%s' is not set in the config\n" % required_key
                message += "please either set it or export CONDUCTOR_%s to the proper value" % required_key.upper()
                logger.error(message)
                raise ValueError(message)
class Auth:
    pass
