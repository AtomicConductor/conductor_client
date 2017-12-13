'''
config module

This module handles all configuration based operations within the Conductor
client tools library
'''

import json
import logging
import multiprocessing
import os
import sys
import yaml

from conductor.lib import common, loggeria

logger = logging.getLogger(__name__)

class Config(object):
    required_keys = []
    default_config = {'base_url': 'atomic-light-001.appspot.com',
                      'thread_count': (multiprocessing.cpu_count() * 2),
                      'instance_cores': 16,
                      'instance_flavor': "standard",
                      'priority': 5,
                      'local_upload': True,
                      'md5_caching': True,
                      'log_level': "INFO"}
    default_config_locations = {'linux2': os.path.join(os.getenv('HOME', ''), '.conductor', 'config.yml'),
                                'win32': os.path.join(os.getenv('APPDATA', ''), 'Conductor Technologies', 'Conductor', 'config.yml'),
                                'darwin': os.path.join(os.getenv('HOME', ''), 'Application Support/Conductor', 'config.yml')}

    def __init__(self):
        logger.debug('base dir is %s', common.base_dir())

        # create config. precedence is default, ENV, CLI
        combined_config = self.default_config
        combined_config.update(self.get_environment_config())
        combined_config.update(self.get_user_config())

        # verify that we have the required params
        self.verify_required_params(combined_config)

        # set the url based on account (unless one was already provided)
        if 'url' not in combined_config:
            combined_config['url'] = 'https://atomic-light-001.appspot.com'

        if 'auth_url' not in combined_config:
            combined_config['auth_url'] = 'https://dashboard.conductortech.com'

        self.validate_api_key(combined_config)
        recombined_config = self.add_api_settings(combined_config)
        self.config = recombined_config
        logger.debug('config is:\n%s', self.config)

    @staticmethod
    def add_api_settings(settings_dict):
        api_url = settings_dict.get("api_url", "https://api.conductortech.com")
        if os.environ.get("LOCAL"):
            api_url = "http://localhost:8081"
        settings_dict["api_url"] = api_url
        return settings_dict

    @staticmethod
    def validate_api_key(config):
        """
        Load the API Key (if it exists)
        Args:
            config: client configuration object

        Returns: None

        """
        if 'api_key_path' not in config:
            config['api_key_path'] = os.path.join(common.base_dir(), 'auth', 'conductor_api_key')
        api_key_path = config['api_key_path']

        #  If the API key doesn't exist, then no biggie, just bail
        if not os.path.exists(api_key_path):
            # config['api_key'] = None
            return
        try:
            with open(api_key_path, 'r') as fp:
                config['api_key'] = json.loads(fp.read())
        except:
            message = "An error occurred reading the API key"
            logger.error(message)
            raise ValueError(message)

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

    @classmethod
    def _process_var_value(cls, env_var):
        '''
        Read the given value (which was read from an environment variable, and
        process it onto an appropriate value for the config.yml file.
        1. cast integers strings to python ints
        2. cast bool strings into actual python bools
        3. anything else?
        '''
        # Cast integers
        if env_var.isdigit():
            return int(env_var)

        # Cast booleans
        bool_values = {"true": True,
                       "false": False}

        return bool_values.get(env_var.lower(), env_var)

    def get_config_file_paths(self):
        if 'CONDUCTOR_CONFIG' in os.environ:
            # We need to take into account multiple paths
            possible_paths = [x for x in os.environ['CONDUCTOR_CONFIG'].split(os.pathsep) if len(x) > 0]
            if len(possible_paths) > 0:
                return possible_paths
        # This is for when CONDUCTOR_CONFIG variable is empty.
        return [self.default_config_locations[sys.platform]]

    @staticmethod
    def create_default_config(path):
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        with open(path, 'w') as config:
            config.write('local_upload: True\n')
            config.write('# api_key_path: <path to conductor_api_key.json>\n')
        return {}

    def get_user_config(self):
        config_files = self.get_config_file_paths()
        for config_file in config_files:
            logger.debug('Attempting to load config located at: %s', config_file)

            if os.path.isfile(config_file):
                logger.debug('Loading config: %s', config_file)
                try:
                    with open(config_file, 'r') as fp:
                        config = yaml.safe_load(fp)
                    if config.__class__.__name__ != 'dict':
                        message = 'config found at %s is not in proper yaml syntax' % config_file
                        logger.error(message)

                    logger.debug('config is %s', config)
                    logger.debug('config.__class__ is %s', config.__class__)
                    return config
                except IOError:
                    message = "could't open config file: %s\n" % config_file
                    message += 'please either create one or set the CONDUCTOR_CONFIG\n'
                    message += 'environment variable to a valid config file\n'
                    message += 'see %s for an example' % os.path.join(common.base_dir(), 'config.example.yml')
                    logger.error(message)
            else:
                logger.warn('Config filepath: %s does not point to a file', config_file)
        logger.warn('No valid config files found, creating default config.yml at {}'.format(config_files[-1]))
        return self.create_default_config(config_files[-1])

    def verify_required_params(self, config):
        logger.debug('config is %s', config)
        for required_key in self.required_keys:
            if required_key not in config:
                message = "required param '%s' is not set in the config\n" % required_key
                message += "please either set it or export CONDUCTOR_%s to the proper value" % required_key.upper()
                logger.error(message)
                raise ValueError(message)


def loadConfig():
    '''
    Create a new config object based on config.yml and return it
    Set up logging based on configuration loaded
    '''
    configuration = Config().config
    # If there is log level specified in config (which by default there should be)
    # then set it for conductor's logger
    log_level = configuration.get("log_level")
    if log_level:
        loggeria.set_conductor_log_level(log_level)
    return configuration

