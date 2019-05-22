import logging
import sys

from conductor.lib import common, loggeria

# The version string is updated by the build system.
# Do not modify the following line.
# __version__="0.0.0"

# Read the config yaml file upon module import
try:
    CONFIG = common.Config().config
except ValueError:
    CONFIG = common.Config().config


class LogLevelFilter(logging.Filter):
    """Filter log messages based on level.

    By default, the logger sends everything to stderr. This is a problem
    in Clarisse at least, because stderr prints RED in the log panel and
    it pops up a floating window to display what it thinks is an error.
    Customers get worried. To alleviate this we make 2 handlers, one for
    stdout and one for stderr, and we route the appropriate log records
    to each. This filter only allows warning, info, and debug records
    and will be used by a handler to log to stdout. The stderr handler
    simply has it's level set for error and critical records only.
    """

    def __init__(self, name=""):
        super(LogLevelFilter, self).__init__(name)

    def filter(self, record):
        return int(record.levelno < logging.ERROR)


logger = logging.getLogger(__name__)

# Handle debug, info, warning records only.
logging_handler_out = logging.StreamHandler(sys.stdout)
logging_handler_out.setLevel(logging.DEBUG)
logging_handler_out.addFilter(LogLevelFilter())
logger.addHandler(logging_handler_out)

# Handle error and critical records only.
logging_handler_err = logging.StreamHandler(sys.stderr)
logging_handler_err.setLevel(logging.ERROR)
logger.addHandler(logging_handler_err)


# If there is log level specified in config (which by default there should
# be), then set it for conductor's logger
log_level = CONFIG.get("log_level")
if log_level:
    loggeria.set_conductor_log_level(log_level)
 