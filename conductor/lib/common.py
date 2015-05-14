import logging
import math
import multiprocessing
import os
import platform
import subprocess
import time
import traceback
import yaml


if os.environ.has_key('DEVELOPMENT'):
    logging.basicConfig(level='DEBUG')
else:
    logging.basicConfig(level='INFO')
    logging.info('set DEVELOPMENT environment variable to get debug messages')


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
            logging.debug('trying to run %s' % function)
            return_values = function()
        except Exception, e:
            print 'caught error'
            logging.debug('failed due to: \n%s' % traceback.format_exc())
            if i < retry_count:
                sleep_time = int(math.pow(2,i))
                logging.debug('retrying after %s seconds' % sleep_time)
                time.sleep(sleep_time)
                i += 1
                continue
            else:
                logging.debug('exceeded %s retries. throwing error...' % retry_count)
                raise e
        else:
            logging.debug('ran %s ok' % function)
            return return_values

def run(cmd):
    logging.debug("about to run command: " + cmd)
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
        'url': 'conductorio.com',
        'thread_count': (multiprocessing.cpu_count() * 2),
    }


    def __init__(self):
        logging.debug('base dir is %s' % self.base_dir())
        user_config = self.get_user_config()
        self.verify_config(user_config)


        combined_config = self.default_config
        combined_config.update(user_config)
        self.config = combined_config
        logging.debug('config is:\n%s' % self.config)



    def base_dir(self):
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

    def get_user_config(self,config_file=None):
        default_config_file = os.path.join(self.base_dir(),'config.yml')

        if os.environ.has_key('CONDUCTOR_CONFIG'):
            config_file = os.environ['CONDUCTOR_CONFIG']
        elif config_file is None:
            config_file = default_config_file
        logging.debug('using config: %s' % config_file)

        try:
            with open(config_file,'r') as file:
                config = yaml.load(file)
        except IOError, e:
            logging.error('could not find a config file at: %s' % config_file)
            logging.error('please either create one at %s' % default_config_file)
            logging.error('or set the CONDUCTOR_CONFIG environment variable to a valid config file')
            raise ValueError

        if config.__class__.__name__ != 'dict':
            logging.error('config found at %s is not in proper yaml syntax' % config_file)
            raise ValueError

        print 'config is %s' % config
        print 'config.__class__ is %s' % config.__class__
        return config

    def verify_config(self,config):
        print 'config is %s' % config
        for required_key in self.required_keys:
            if not required_key in config:
                logging.error("required param '%s' is not set in the config" % required_key)
                raise ValueError
class Auth:
    pass
