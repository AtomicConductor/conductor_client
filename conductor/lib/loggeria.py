import os
import logging
import logging.handlers



LEVEL_CRITICAL = "CRITICAL"
LEVEL_ERROR = "ERROR"
LEVEL_WARNING = "WARNING"
LEVEL_INFO = "INFO"
LEVEL_DEBUG = "DEBUG"
LEVEL_NOTSET = "NOTSET"

LEVELS = [LEVEL_CRITICAL, LEVEL_ERROR, LEVEL_WARNING, LEVEL_INFO, LEVEL_DEBUG, LEVEL_NOTSET]


LEVEL_MAP = {LEVEL_CRITICAL: logging.CRITICAL,
             LEVEL_ERROR: logging.ERROR,
             LEVEL_WARNING: logging.WARNING,
             LEVEL_INFO: logging.INFO,
             LEVEL_DEBUG: logging.DEBUG,
             LEVEL_NOTSET: logging.NOTSET}


FORMATTER_LIGHT = logging.Formatter('%(asctime)s %(name)s: %(message)s', "%Y-%m-%d %H:%M:%S")
FORMATTER_VERBOSE = logging.Formatter('%(asctime)s %(name)s%(levelname)9s:  %(message)s')
DEFAULT_LEVEL_CONSOLE = LEVEL_INFO
DEFAULT_LEVEL_FILE = LEVEL_DEBUG
DEFAULT_LEVEL_LOGGER = LEVEL_INFO

CONDUCTOR_LOGGER_NAME = "conductor"


def setup_conductor_logging(logger_level=DEFAULT_LEVEL_LOGGER,
                            console_level=None,
                            console_formatter=FORMATTER_LIGHT,
                            log_filepath=None,
                            file_level=None,
                            file_formatter=FORMATTER_VERBOSE):
    '''
    The is convenience function to help set up logging. 
    
    THIS SHOULD ONLY BE CALLED ONCE within an execution environment.

    
    This function does the following:
    
    1. Creates/retrieves the logger object for the "conductor" package
    2. Sets that logger's  log level to the given logger_level (optional)
    3. Creates a console handler and attaches it to the logger object. 
    3a. Optionally sets that console handler's log level to the given console_level
    3b. Optionally sets that console handler's formatter to the the given console_formatter
    4.  Optionally creates a file handler (if a log filepath is given) 
    4a. Optionally sets that file handler's log level to the given file_level
    4b. Optionally sets that file handler's formatter to the the given file_formatter

    console_formatter & file_formatter:
    Formatters are the formatter objects. Not just a string such as "DEBUG".  
    This is because you may need more than just a string to define a formatter object.
    '''
    # Get the top/parent conductor logger
    logger = get_conductor_logger()
    if logger_level:
        assert logger_level in LEVEL_MAP.values(), "Not a valid log level: %s" % logger_level
        # Set the main log level. Note that if this is super restrive, you won't see handler messages, regardless of the handlers' log level
        logger.setLevel(logger_level)

        # Console handler for outputting log to screen
    console_handler = logging.StreamHandler()
    logger.addHandler(console_handler)

    # create formatter and apply it to the handlers
    if console_formatter:
        console_handler.setFormatter(console_formatter)

    # Set the console log level (note that the main logger object will make this irrelevant if the main logger's level is too restricitve)
    if console_level:
        assert console_level in LEVEL_MAP.values(), "Not a valid log level: %s" % console_level
        console_handler.setLevel(console_level)

    # Create a file handler if a filepath was given
    if log_filepath:
        if file_level:
            assert file_level in LEVEL_MAP.values(), "Not a valid log level: %s" % file_level
        # Rotating file handler. Rotates every day (24 hours). Stores 7 days at a time.
        file_handler = create_file_handler(log_filepath, level=file_level, formatter=file_formatter)
        logger.addHandler(file_handler)



def create_file_handler(filepath, level=None, formatter=None):
    '''
    Create a file handler object for the given filepath.
    This is a ROTATING file handler, which rotates every day (24 hours) and 
    stores up to 7 days of logs at a time (equalling up to as many as 7 log files 
    at a given time.
    '''

    log_dirpath = os.path.dirname(filepath)
    if not os.path.exists(log_dirpath):
        os.makedirs(log_dirpath)

    # Rotating file handler. Rotates every day (24 hours). Stores 7 days at a time.
    handler = logging.handlers.TimedRotatingFileHandler(filepath,
                                                        interval=24,
                                                        backupCount=7)
    if formatter:
        handler.setFormatter(formatter)

    if level:
        handler.setLevel(level)

    return handler


def set_conductor_log_level(log_level):
    '''
    Set the "conductor" package's logger to the given log level
    '''
    assert log_level in LEVEL_MAP.keys(), "Invalid log_level: %s" % log_level
#     assert log_level in LEVEL_MAP.values(), "Invalid log_level: %s" % log_level
    logger = get_conductor_logger()
    logger.setLevel(log_level)


def get_conductor_logger():
    '''
    Return the "conductor" package's logger object
    '''
    return logging.getLogger(CONDUCTOR_LOGGER_NAME)


# def get_logger_handlers(logger, handler_types=()):
#     '''
#     Return the handlers for the given logger.  Optionally filter which types
#     of handlers to return
#     '''
#     handlers = []
#
#     for handler in logger.handlers:
#         if not handler_types or handler.__class__ in handler_types:
#             handlers.append(handler)
#     return handlers
#
# def set_file_handler_filepath(logger, filepath):
#     '''
#     Set the file handler to write to a different filepath.
#
#     This is actually a hack because you can't have a filehandler start writing
#     to a new filepath. The handler needs to be deleted and recreated to point
#     to the new location.
#     '''
#     file_handler_classes = [logging.FileHandler,
#                             logging.handlers.RotatingFileHandler,
#                             logging.handlers.TimedRotatingFileHandler]
#     file_handlers = get_logger_handlers(logger, handler_types=file_handler_classes)
#
#     if len(file_handlers) != 1:
#         raise Exception("Did not get exactly one file handler object: %s", file_handlers)
#
#     old_file_handler = file_handlers[0]
#     new_file_handler = create_file_handler(filepath, level=old_file_handler.level,
#                                            formatter=old_file_handler.formatter)
#
#     logger.removeHandler(old_file_handler)
#     logger.addHandler(new_file_handler)


