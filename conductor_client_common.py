import os
import logging
import logging.handlers
import socket

# Setup Dev/Prod environment
if os.environ.has_key('DEVELOPMENT'):
    BUCKET_NAME = 'conductor'
    CONDUCTOR_URL = "http://localhost:8080/"
    LOG_LEVEL = "DEBUG"
    FILE_FORMATTER = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    CONSOLE_FORMATTER = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
else:
    BUCKET_NAME = 'output_render'
    CONDUCTOR_URL = "https://3-dot-atomic-light-001.appspot.com/"
    LOG_LEVEL = "INFO"
    FILE_FORMATTER = logging.Formatter('%(asctime)s - %(hostname)s - %(levelname)s - %(message)s')
    CONSOLE_FORMATTER = logging.Formatter('%(asctime)s - %(message)s')


class ContextFilter(logging.Filter):
    """ Logging filter to get hostname """
    # pylint: disable=too-few-public-methods
    hostname = socket.gethostname()

    def filter(self, record):
        """ set the hostname """
        record.hostname = ContextFilter.hostname
        return True

def get_temp_dir():
    try:
        tmp_dir = os.environ['TEMP']
    except KeyError, excp:
        if os.name == "nt":
            tmp_dir = "C:/TEMP/Conductor_Logs"
        else:
            tmp_dir = "/tmp/conductor_logs"
    return tmp_dir

def make_destination_dir(destination_dir):
    """ If the destination dir does not exist, create it """
    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir, 0775)

def setup_logger(name, log_dir=None):
    """ Create a logging instance """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))
    log_filter = ContextFilter()
    logger.addFilter(log_filter)
    if log_dir is not None:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_file = "%s/%s.log" % (log_dir, name)
    else:
        log_file = "/var/log/%s.log" % name
    if not os.path.exists(log_file):
        with open(log_file, 'w') as file_obj:
            file_obj.write("Starting %s log..." % name)
    fh = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=2560000,
        backupCount=2
        )
    fh.setLevel(getattr(logging, LOG_LEVEL))
    fh.setFormatter(FILE_FORMATTER)
    ch = logging.StreamHandler()
    ch.setLevel(getattr(logging, LOG_LEVEL))
    ch.setFormatter(CONSOLE_FORMATTER)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger
