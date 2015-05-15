import logging
import math
import multiprocessing
import os
import platform
import subprocess
import time
import traceback
import yaml

def setup_logger():
    """ This function is called when this file is imported!
    Returns a general formatted logging object.
    """
    logger = logging.getLogger("ConductorClient")
    if os.environ.has_key('CONDUCTOR_DEVELOPMENT'):
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s -  %(message)s')
    else:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s -  %(message)s')
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger

# Global logger object, don't use this object directly.
# It is preferred to use the conductor.logger in the conductor __init__.py
# except within this file
LOGGER = setup_logger()

###
# Global Functions
###

def retry(function,retry_count=5):
    # disable retries in testing
    if os.environ['FLASK_CONF'] == 'TEST':
        retry_count = 0

    i=0
    while True:
        try:
            LOGGER.debug('trying to run %s' % function)
            return_values = function()
        except Exception, e:
            print 'caught error'
            LOGGER.debug('failed due to: \n%s' % traceback.format_exc())
            if i < retry_count:
                sleep_time = int(math.pow(2,i))
                LOGGER.debug('retrying after %s seconds' % sleep_time)
                time.sleep(sleep_time)
                i += 1
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


class Config():
    required_keys = ['account']
    default_config = {
        # TODO
        'base_url': 'atomic-light-001.appspot.com',
        'thread_count': (multiprocessing.cpu_count() * 2),
    }

    def __init__(self):
        LOGGER.debug('base dir is %s' % self.base_dir())
        user_config = self.get_user_config()
        self.verify_config(user_config)


        combined_config = self.default_config
        combined_config.update(user_config)
        if not 'url' in combined_config:
            combined_config['url'] = 'https://%s-dot-%s' % (combined_config['account'],
                                                            combined_config['base_url'])
        self.config = combined_config
        LOGGER.debug('config is:\n%s' % self.config)



    def base_dir(self):
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

    def get_user_config(self,config_file=None):
        default_config_file = os.path.join(self.base_dir(),'config.yml')

        if os.environ.has_key('CONDUCTOR_CONFIG'):
            config_file = os.environ['CONDUCTOR_CONFIG']
        elif config_file is None:
            config_file = default_config_file
        LOGGER.debug('using config: %s' % config_file)

        try:
            with open(config_file,'r') as file:
                config = yaml.load(file)
        except IOError, e:
            message = 'could not find a config file at: %s' % config_file
            message += 'please either create one at %s' % default_config_file
            message += 'or set the CONDUCTOR_CONFIG environment variable to a valid config file'
            message += 'see %s for an example' % os.path.join(self.base_dir(),'config.example.yml')
            LOGGER.error(message)
            raise ValueError(message)

        if config.__class__.__name__ != 'dict':
            message = 'config found at %s is not in proper yaml syntax' % config_file
            LOGGER.error(message)
            raise ValueError(message)

        print 'config is %s' % config
        print 'config.__class__ is %s' % config.__class__
        return config

    def verify_config(self,config):
        print 'config is %s' % config
        for required_key in self.required_keys:
            if not required_key in config:
                message = "required param '%s' is not set in the config" % required_key
                LOGGER.error(message)
                raise ValueError(message)
class Auth:
    pass
