import functools
import logging
import os
import yappi
import time
import tempfile

from conductor.lib import common

# Set the logger for the module.
logger = logging.getLogger(__name__)


class YappiProfile(object):
    VAR_PROFILING_ENABLED = "CONDUCTOR_PROFILE"
    VAR_PROFILE_DIR = "CONDUCTOR_PROFILE_DIR"

    def __call__(self, function):
        '''
        This gets called during python compile time (as all decorators do).
        It will always have only a single argument: the function this is being
        decorated.  It's responsibility is to return a callable, e.g. the actual
        decorator function 
        '''

        @functools.wraps(function)
        def decorater_function(*args, **kwargs):
            profiling_enabled = common.is_env_variable_on(self.VAR_PROFILING_ENABLED)
            logger.debug("Performance profiling enabled: %s", profiling_enabled)

            # If profiling is not enabled, then simply call/return  the original function
            if not profiling_enabled:
                return function(*args, **kwargs)

            # Create directory for profiling data
            profile_dirpath = os.environ.get(self.VAR_PROFILE_DIR) or tempfile.gettempdir()
            if not os.path.isdir(profile_dirpath):
                os.makedirs(profile_dirpath)

            self.start_time = time.time()
            self.start_profiling(profile_dirpath)

            try:
                results = function(*args, **kwargs)
            except:
                results = None
                raise
            finally:
                self.stop_profiling(profile_dirpath)
                return results

        return decorater_function

    @classmethod
    def start_profiling(cls, data_dirpath):

        # start profiling
        logger.info('starting Yappi profiling...')
        yappi.start()

    def stop_profiling(self, data_dirpath):
        logger.info('stopping Yappi profiling')
        if yappi.is_running():
            yappi.stop()

        now = int(time.time())
        duration = int(now - self.start_time)

        # Write thread stats
        thread_filename = '{}_thread-{}s.txt'.format(now, duration)
        profile_thread_filepath = os.path.join(data_dirpath, thread_filename)
        thread_stats = yappi.get_thread_stats()
        logger.info("Writing thread profiling stats to: %s", profile_thread_filepath)
        with open(profile_thread_filepath, 'w') as f:
            thread_stats.print_all(f)

        # Write function stats
        func_stats = yappi.get_func_stats()
        func_pstats = yappi.convert2pstats(func_stats)
        func_filename = '{}_function-{}s.profile'.format(now, duration)
        profile_func_filepath = os.path.join(data_dirpath, func_filename)
        logger.info("Writing function profiling stats to: %s", profile_func_filepath)
        func_pstats.dump_stats(profile_func_filepath)
