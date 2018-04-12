import base64
import datetime
import functools
import hashlib
import json
import logging
import multiprocessing
import os
import platform
import random
import signal
import subprocess
import sys
import time
import traceback
import yaml

BYTES_1KB = 1024
BYTES_1MB = BYTES_1KB ** 2
BYTES_1GB = BYTES_1KB ** 3
BYTES_1TB = BYTES_1KB ** 4


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


class ExceptionAction(object):
    '''
    This is a base class to be used for constructing decorators that take a
    specific action when the decorated method/function raises an exception.
    For example, it can send a message or record data to a database before
    the exception is raised, and then (optionally) raise the exception.
    Optionally specify particular exceptions (classes) to be omiited from taking
    action on (though still raise the exception)

    disable_var: str. An environment variable name, which if found in the runtime
                      environement will disable the action from being taken. This
                      can be useful when a developer is activeky developing and
                      does not want the decorator to take action.
    '''

    def __init__(self, raise_=True, omitted_exceptions=(), disable_var=""):
        self.omitted_exceptions = omitted_exceptions
        self.raise_ = raise_
        self.disable_var = disable_var

    def __call__(self, function):
        '''
        This gets called during python compile time (as all decorators do).
        It will always have only a single argument: the function this is being
        decorated.  It's responsbility is to return a callable, e.g. the actual
        decorator function
        '''
        @functools.wraps(function)
        def decorater_function(*args, **kwargs):
            '''
            The decorator function

            Tries to execute the decorated function. If an exception occurs,
            it is caught, takes the action, and then raises the exception.
            '''

            try:
                return function(*args, **kwargs)
            except Exception as e:
                # IF the exception is one that is to be ignored, then simply raise
                # it. No further action to take
                if isinstance(e, self.omitted_exceptions) or (self.disable_var and os.environ.get(self.disable_var)):
                    logger.debug("Skipping exception action")
                    raise

                # Wrap the action in a try/except so that this decorator does
                # not block/disrupt the behavior of the wrapped function/method
                try:
                    self.take_action(e)
                except:
                    failed_method_name = "%s.%s.%s" % (__name__, self.__class__.__name__, self.take_action.__name__)
                    logger.error("%s failed:\n%s", failed_method_name, traceback.format_exc())

                # Raise the original exception if indicated to do so
                if self.raise_:
                    raise e

        return decorater_function

    def take_action(self, e):
        '''
        Overide this method to do something useful before raising the exception.

        e.g.:
            print "sending error message to mom: %s" % traceback.format_exc()
        '''
        raise NotImplementedError


class ExceptionLogger(ExceptionAction):
    '''
    DECORATOR
    If the decorated function raises an exception, this decorator can log
    the exception and continue (suppressing the actual exception.  A message
    may be prepended to the exception message.

    example output:

        >> broken_function()
        # Warning: conductor.lib.common : My prependend message
        Traceback (most recent call last):
          File "/usr/local/lschlosser/code/conductor_client/conductor/lib/common.py", line 85, in decorater_function
            return function(*args, **kwargs)
          File "<maya console>", line 4, in broken_function
        ZeroDivisionError: integer division or modulo by zero


    '''

    def __init__(self, message="", log_traceback=True, log_level=logging.WARNING,
                 raise_=False, omitted_exceptions=(), disable_var=""):
        '''
        message: str. The prepended message
        log_level: int. The log level to log the message as
        raise_: bool.  Whether to raise (i.e. not supress) the exception after
                it's been logged.
        '''

        self._message = message
        self._log_traceback = log_traceback
        self._log_level = log_level
        super(ExceptionLogger, self).__init__(raise_=raise_,
                                              omitted_exceptions=omitted_exceptions,
                                              disable_var=disable_var)

    def take_action(self, error):
        '''
        Log out the message
        '''
        msg = ""
        if self._message:
            msg += self._message
        if self._log_traceback:
            # check if msg is empty or not.  Don't want to add a newline to empty line.
            if msg:
                msg += "\n"
            msg += traceback.format_exc()
        logger.log(self._log_level, msg)


def dec_timer_exit(log_level=logging.INFO):
    def timer_decorator(func):
        '''
        '''
        @functools.wraps(func)
        def wrapper(*a, **kw):
            func_name = getattr(func, "__name__", "<Unknown function>")
            start_time = time.time()
            result = func(*a, **kw)
            finish_time = '%s :%.2f seconds' % (func_name, time.time() - start_time)
            logger.log(log_level, finish_time)
            return result
        return wrapper

    return timer_decorator


def dec_catch_exception(raise_=False):
    '''
    DECORATOR
    Wraps the decorated function/method so that if the function raises an
    exception, the exception will be caught, it's message will be printed, and
    optionally the function will return (suppressing the exception) .
    '''
    def catch_decorator(func):

        @functools.wraps(func)
        def wrapper(*args, **kwds):
            try:
                return func(*args, **kwds)
            except:
                func_name = getattr(func, "__name__", "<Unknown function>")
                stack_str = "".join(traceback.format_exception(*sys.exc_info()))
                msg = ('\n#############################################\n'
                       'Failed to call "%s". Caught traceback stack:\n'
                       '%s\n'
                       '#############################################' % (func_name, stack_str))
                logger.error(msg)
                if raise_:
                    raise
        return wrapper
    return catch_decorator


class DecRetry(object):
    '''
    Decorator that retries the decorated function using an exponential backoff sleep.

    retry_exceptions: An Exception class (or a tuple of Exception classes) that
                    this decorator will catch/retry.  All other exceptions that
                    occur will NOT be retried. By default, all exceptions are
                    caught (due to the default arguemnt of Exception)

    skip_exceptions:  An Exception class (or a tuple of Exception classes) that
                     this decorator will NOT catch/retry.  This will take precedence
                     over the retry_exceptions.

    tries: int. number of times to try (not retry) before raising
    static_sleep: The amount of seconds to sleep before retrying. When set to
                  None, the sleep time will use exponential backoff. See below.

    This retry function not only incorporates exponential backoff, but also
    "jitter".  see http://www.awsarchitectureblog.com/2015/03/backoff.html.
    Instead of merely increasing the backoff time exponentially (determininstically),
    there is a randomness added that will set the sleeptime anywhere between
    0 and the full exponential backoff time length.

    '''

    def __init__(self, retry_exceptions=Exception, skip_exceptions=(), tries=8, static_sleep=None):
        self.retry_exceptions = retry_exceptions
        self.skip_exceptions = skip_exceptions
        self.tries = tries
        self.static_sleep = static_sleep

    def __call__(self, orig_function):

        @functools.wraps(orig_function)
        def wrapper_function(*args, **kwargs):

            # Attempt to call the function in a try/excet as many times as specified by the tries, minus 1)
            # if tries=1, this loop wont even happen
            for try_num in range(self.tries - 1):
                try:
                    return orig_function(*args, **kwargs)
                except Exception as e:
                    if not isinstance(e, self.retry_exceptions) or isinstance(e, self.skip_exceptions):
                        logger.debug("Skipping retry because mismatched exception type: %s", type(e))
                        raise
                    if self.static_sleep is not None:
                        sleep_time = self.static_sleep
                    else:
                        # use random for jitter.
                        sleep_time = random.randrange(0, 2 ** try_num)
                    msg = "%s, Retrying in %d seconds..." % (str(e), sleep_time)
                    logger.warning(msg)
                    self.sleep(sleep_time)

            # if we've gotten here, we've run out of retries. This is the last try.
            # This will be unhandled exception if it fails.
            return orig_function(*args, **kwargs)
        return wrapper_function

    def sleep(self, seconds):
        time.sleep(seconds)


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


def generate_md5(filepath, base_64=False, blocksize=65536, poll_seconds=None,
                 callback=None, log_level=logging.INFO):
    '''
    Generate and return md5 hash (base64) for the given filepath

    filepath: str. The file path to generate an md5 hash for.

    base_64: bool. whether or not to return a base64 string.

    poll_seconds: int, the number of seconds to wait between logging out to the
                   console when md5 hashing (particularly a large file which
                   may take a while)
    log_level: logging.level. The log level that should be used
                when logging messages.

   callback: A callable that is called during the md5 hashing process. It's called
             every time a block of data has been hashed (see blocksize arg).The
             callable receives the following arguments:

             filepath: see above

             file_size: the total size of the file (in bytes)

             bytes_processed: the amount of bytes that has currently been hashed

             log_level: see above

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
        bytes_processed = buffer_count * blocksize
        percentage_processed = int((bytes_processed / float(file_size)) * 100)

        if poll_seconds and curtime - last_time >= poll_seconds:
            logger.log(log_level, "MD5 hashing %s%% (size %s bytes): %s ",
                       percentage_processed, file_size, filepath)
            last_time = curtime

        if callback:
            callback(filepath, file_size, bytes_processed, log_level=log_level)

        buffer_count += 1

    md5 = hash_obj.digest()

    logger.log(log_level, "MD5 hashing 100%% (size %s bytes): %s ", file_size, filepath)
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
    required_keys = []
    default_config = {'base_url': 'atomic-light-001.appspot.com',
                      'thread_count': min(multiprocessing.cpu_count() * 2, 16),  # cap the default thread count at 16
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
        logger.debug('base dir is %s' % base_dir())

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
        logger.debug('config is:\n%s' % self.config)

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
            config['api_key_path'] = os.path.join(base_dir(), 'auth', 'conductor_api_key')
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

    def _process_var_value(self, env_var):
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

    def get_config_file_paths(self, config_file=None):
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
            logger.debug('Attempting to load config located at: %s' % config_file)

            if os.path.isfile(config_file):
                logger.debug('Loading config: %s', config_file)
                try:
                    with open(config_file, 'r') as fp:
                        config = yaml.safe_load(fp)
                    if config.__class__.__name__ != 'dict':
                        message = 'config found at %s is not in proper yaml syntax' % config_file
                        logger.error(message)

                    logger.debug('config is %s' % config)
                    logger.debug('config.__class__ is %s' % config.__class__)
                    return config
                except IOError:
                    message = "could't open config file: %s\n" % config_file
                    message += 'please either create one or set the CONDUCTOR_CONFIG\n'
                    message += 'environment variable to a valid config file\n'
                    message += 'see %s for an example' % os.path.join(base_dir(), 'config.example.yml')
                    logger.error(message)
            else:
                logger.warn('Config filepath: %s does not point to a file', config_file)
        logger.warn('No valid config files found, creating default config.yml at {}'.format(config_files[-1]))
        return self.create_default_config(config_files[-1])

    def verify_required_params(self, config):
        logger.debug('config is %s' % config)
        for required_key in self.required_keys:
            if required_key not in config:
                message = "required param '%s' is not set in the config\n" % required_key
                message += "please either set it or export CONDUCTOR_%s to the proper value" % required_key.upper()
                logger.error(message)
                raise ValueError(message)


def load_resources_file():
    '''
    Return the resource yaml file as a dict.

    If the $CONDUCTOR_RESOURCES_PATH environment variable is set, then use it
    to find load the resource file from. Otherwise look for it in the default
    location.

    TODO:(lws) the resource filepath should also be able to be dictated in the config
    But can't check that here because this module (common.py) should not
    have any imports from the conductor package, i.e. this module creates the
    config, and therefore cannot be reliant on the config.
    '''

    resources_filepath = os.environ.get("CONDUCTOR_RESOURCES_PATH")

    if not resources_filepath:
        resources_filepath = os.path.join(base_dir(), "conductor", "resources", "resources.yml")

    with open(resources_filepath, 'r') as file_:
        return yaml.safe_load(file_)


def get_conductor_instance_types():
    '''
    Get the list of available instances types from the resources.yml file
    '''
    resources = load_resources_file()
    return resources.get("instance_types") or []


def get_conductor_gpu_configs():
    '''
    Get the list of available GPU configs from the resources.yml file
    '''
    resources = load_resources_file()
    return resources.get("gpu_configs") or []


def get_package_ids():
    '''
    Get the list of available instances types from the resources.yml file
    '''
    resources = load_resources_file()
    return resources.get("package_ids") or {}


def get_human_bytes(bytes_):
    '''
    For the given bytes (integer), convert and return a "human friendly:
    representation of that data size.
    '''
    if bytes_ > BYTES_1TB:
        return "%.2fTB" % (bytes_ / float(BYTES_1TB))
    elif bytes_ > BYTES_1GB:
        return "%.2fGB" % (bytes_ / float(BYTES_1GB))
    elif bytes_ > BYTES_1MB:
        return "%.2fMB" % (bytes_ / float(BYTES_1MB))
    return "%.2fKB" % (bytes_ / float(BYTES_1KB))


def get_progress_percentage(current, total):
    '''
    Return  a string percentage, e.g. "80%" given current bytes (int) and total
    bytes (int)
    '''
    if not all([current, total]):
        progress_int = 0
    else:
        progress_int = int(current / float(total) * 100)
    return "%s%%" % progress_int


def get_human_duration(seconds):
    '''
    convert the given seconds (float) into a human friendly unit
    '''
    return str(datetime.timedelta(seconds=round(seconds)))


def get_human_timestamp(seconds_since_epoch):
    '''
    convert the given seconds since epoch (float)
    '''
    return str(datetime.datetime.fromtimestamp(int(seconds_since_epoch)))


def load_yaml(filepath, safe=True, omit_tags=False):
    '''
    Helper class that loads the given yaml filepath into a python object.

    safe: bool. When True, will use yaml's safe_loader.

    omit_tags: bool. When True, will skip any yaml tags in the file. This can be
                useful when you want to read a yaml file but don't have all
                of the necessary yaml tag constructors to do so.  All tags in the file
                will be given a value of u'<TAG OMITTED>'

    This function is somewhat complex(and ugly) because it must create it's own functions and classes.
    The reason it must create it's own Loader class is because when adding a custom constructor,
    that constructor remains loaded (and imbedded in the PyYaml's native Loader class) for the
    duration of the python session. This could lead to disastrous behavior for customers that may
    be using the same session to do additional python work (think inside of Maya).  So instead
    of using PyYaml's Loader classes directly, we subclass our own so that we can dispose of it when
    we're done. This all could have been avoided if PyYaml also provided a "remove_multi_constructor"
    function.
    '''

    loader = yaml.SafeLoader if safe else yaml.Loader

    def ommitter_constructor(loader, tag_suffix, node):
        '''
        Instead of loading the yaml tag as an object, simply return a string that
        indicated that it was omitted.
        '''
        return tag_suffix + u' <TAG OMITTED>'

    if omit_tags:
        # Create our own Loader class and add our omission constructor to it
        class TmpLoader(loader):
            pass
        loader = TmpLoader
        yaml.add_multi_constructor(u'', ommitter_constructor, Loader=loader)

    logger.debug("Using yaml loader: %s", loader.__name__)

    with open(filepath) as f:
        return yaml.load(f, loader)  # nosec  (ignore bandit static analysis warning for not using safe_load [B506:yaml_load] )
