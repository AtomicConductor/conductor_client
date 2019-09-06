import logging
import logging.handlers
import multiprocessing
import os
import sys
import threading
import traceback
from logging.handlers import TimedRotatingFileHandler

LEVEL_CRITICAL = "CRITICAL"
LEVEL_ERROR = "ERROR"
LEVEL_WARNING = "WARNING"
LEVEL_INFO = "INFO"
LEVEL_DEBUG = "DEBUG"
LEVEL_NOTSET = "NOTSET"

LEVELS = [
    LEVEL_CRITICAL,
    LEVEL_ERROR,
    LEVEL_WARNING,
    LEVEL_INFO,
    LEVEL_DEBUG,
    LEVEL_NOTSET]


LEVEL_MAP = {LEVEL_CRITICAL: logging.CRITICAL,
             LEVEL_ERROR: logging.ERROR,
             LEVEL_WARNING: logging.WARNING,
             LEVEL_INFO: logging.INFO,
             LEVEL_DEBUG: logging.DEBUG,
             LEVEL_NOTSET: logging.NOTSET}


FORMATTER_LIGHT = logging.Formatter(
    '%(asctime)s %(name)s: %(message)s',
    "%Y-%m-%d %H:%M:%S")
FORMATTER_VERBOSE = logging.Formatter(
    '%(asctime)s %(name)s%(levelname)9s:  %(message)s')
DEFAULT_LEVEL_CONSOLE = LEVEL_MAP[LEVEL_INFO]
DEFAULT_LEVEL_FILE = LEVEL_MAP[LEVEL_DEBUG]
DEFAULT_LEVEL_LOGGER = LEVEL_MAP[LEVEL_INFO]

CONDUCTOR_LOGGER_NAME = "conductor"


class LogLevelFilter(logging.Filter):
    """Filter log messages based on level.

    By default, the logger sends everything to stderr. This is a problem
    in Clarisse at least, because stderr prints RED in the log panel and
    pops up a floating window to display what it thinks is an error.
    Customers get worried. To alleviate this we make 2 handlers, one for
    stdout and one for stderr, and we route the appropriate log records
    to each. This filter only allows warning, info, and debug records
    and will be used by the handler that logs to stdout. The stderr
    handler doesn't need a filter as it simply has it's level set for
    error and critical records only.
    """

    def __init__(self, name=""):
        super(LogLevelFilter, self).__init__(name)

    def filter(self, record):
        return int(record.levelno < logging.ERROR)


def setup_conductor_logging(logger_level=DEFAULT_LEVEL_LOGGER,
                            console_level=None,
                            console_formatter=FORMATTER_LIGHT,
                            log_filepath=None,
                            file_level=None,
                            file_formatter=FORMATTER_VERBOSE,
                            multiproc=False):
    """The is convenience function to help set up logging.

    THIS SHOULD ONLY BE CALLED ONCE within an execution environment.

    This function does the following:

    1. Creates/retrieves the logger object for the "conductor" package
    2. Sets that logger's  log level to the given logger_level (optional)
    3. Creates two console handlers (stderr and stdout) and attaches them to the logger object.
    3a. Optionally sets that console handler's formatter to the the given console_formatter
    4.  Optionally creates a file handler (if a log filepath is given)
    4a. Optionally sets that file handler's log level to the given file_level
    4b. Optionally sets that file handler's formatter to the the given file_formatter

    console_formatter & file_formatter:
    Formatters are the formatter objects. Not just a string such as "DEBUG".
    This is because you may need more than just a string to define a formatter object.

    multiproc: bool. If True, a custom file handler will be used that handles multiprocess
               logging correctly. This file handler creates an additional Process.
    """
    # Get the top/parent conductor logger
    logger = get_conductor_logger()

    if logger_level:
        assert logger_level in LEVEL_MAP.values(), "Not a valid log level: %s" % logger_level
        # Set the main log level. Note that if this is super restrive, you
        # won't see handler messages, regardless of the handlers' log level
        logger.setLevel(logger_level)

    # Handle debug, info, warning records only. STDOUT
    console_handler_out = logging.StreamHandler(sys.stdout)
    console_handler_out.setLevel(logging.DEBUG)
    console_handler_out.addFilter(LogLevelFilter())
    logger.addHandler(console_handler_out)

    # Handle error and critical records only. STDERR
    console_handler_err = logging.StreamHandler(sys.stderr)
    console_handler_err.setLevel(logging.ERROR)
    logger.addHandler(console_handler_err)

    # create formatter and apply it to the handlers
    if console_formatter:
        console_handler_out.setFormatter(console_formatter)
        console_handler_err.setFormatter(console_formatter)


    # Create a file handler if a filepath was given
    if log_filepath:
        if file_level:
            assert file_level in LEVEL_MAP.values(), "Not a valid log level: %s" % file_level
        # Rotating file handler. Rotates every day (24 hours). Stores 7 days at
        # a time.
        file_handler = create_file_handler(
            log_filepath,
            level=file_level,
            formatter=file_formatter,
            multiproc=multiproc)
        logger.addHandler(file_handler)


def create_file_handler(filepath, level=None, formatter=None, multiproc=False):
    """Create a file handler object for the given filepath.

    This is a ROTATING file handler, which rotates every day (24 hours)
    and stores up to 7 days of logs at a time (equaling up to as many as
    7 log files at a given time.
    """
    when = 'h'  # rotate unit is "h" (hours)
    interval = 24  # rotate every  24 units (24 hours)
    backupCount = 7  # Retain up to 7 log files (7 days of log files)

    log_dirpath = os.path.dirname(filepath)
    if not os.path.exists(log_dirpath):
        os.makedirs(log_dirpath)

    if multiproc:
        # Use custom rotating file handler that handles multiprocessing
        # properly
        handler = MPFileHandler(
            filepath,
            when=when,
            interval=interval,
            backupCount=backupCount)
    else:
        # Rotating file handler. Rotates every day (24 hours). Stores 7 days at
        # a time.
        handler = logging.handlers.TimedRotatingFileHandler(
            filepath, when=when, interval=interval, backupCount=backupCount)
    if formatter:
        handler.setFormatter(formatter)

    if level:
        handler.setLevel(level)

    return handler


def set_conductor_log_level(log_level):
    """Set the "conductor" package's logger to the given log level."""
    assert log_level in LEVEL_MAP.keys(), "Invalid log_level: %s" % log_level
    logger = get_conductor_logger()
    logger.setLevel(log_level)
    logger.info("Changed log level to %s", log_level)


def get_conductor_logger():
    """Return the "conductor" package's logger object."""
    return logging.getLogger(CONDUCTOR_LOGGER_NAME)


class MPFileHandler(logging.Handler):
    """Multiprocess-safe Rotating File Handler.

    Copied from: http://stackoverflow.com/questions/641420/how-should-i-log-while-using-multiprocessing-in-python
    """

    def __init__(
            self,
            filename,
            when='h',
            interval=1,
            backupCount=0,
            encoding=None,
            delay=0,
            utc=0):
        """See TimedRotatingFileHandler for arg docs."""
        logging.Handler.__init__(self)
        self._handler = TimedRotatingFileHandler(filename,
                                                 when=when,
                                                 interval=interval,
                                                 backupCount=backupCount,
                                                 encoding=encoding,
                                                 delay=delay,
                                                 utc=utc)

        self.queue = multiprocessing.Queue()

        t = threading.Thread(target=self.receive)
        t.daemon = True
        t.start()

    def setFormatter(self, fmt):
        logging.Handler.setFormatter(self, fmt)
        self._handler.setFormatter(fmt)

    def receive(self):
        while True:
            try:
                record = self.queue.get()
                self._handler.emit(record)
            except (KeyboardInterrupt, SystemExit):
                raise
            except EOFError:
                break
            except BaseException:
                traceback.print_exc(file=sys.stderr)

    def send(self, s):
        self.queue.put_nowait(s)

    def _format_record(self, record):
        # ensure that exc_info and args
        # have been stringified.  Removes any chance of
        # unpickleable things inside and possibly reduces
        # message size sent over the pipe
        if record.args:
            record.msg = record.msg % record.args
            record.args = None
        if record.exc_info:
            dummy = self.format(record)
            record.exc_info = None

        return record

    def emit(self, record):
        try:
            s = self._format_record(record)
            self.send(s)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            self.handleError(record)

    def close(self):
        self._handler.close()
        logging.Handler.close(self)


class TableStr(object):
    '''
    A class to help log/print tables of data
    
    ############## DOWNLOAD HISTORY #################
    COMPLETED AT         DOWNLOAD ID       JOB    TASK       SIZE  ACTION  DURATION  THREAD     FILEPATH
    2016-01-16 01:12:46  5228833175240704  00208  010    137.51MB  DL      0:00:57   Thread-12  /tmp/conductor_daemon_dl/04/cental/cental.010.exr
    2016-01-16 01:12:42  6032237141164032  00208  004    145.48MB  DL      0:02:24   Thread-2   /tmp/conductor_daemon_dl/04/cental/cental.004.exr
    2016-01-16 01:12:40  5273802288136192  00208  012    140.86MB  DL      0:02:02   Thread-16  /tmp/conductor_daemon_dl/04/cental/cental.012.exr
    '''

    # A dict which contains callable functions that can be used 
    # to condition each column entry of the table
    header_modifiers = {}

    cell_modifiers = {}

    # The characters to print between the columns (to separate them)
    column_spacer = "  "

    row_spacer = "\n"

    def __init__(
            self,
            data,
            column_names,
            title="",
            footer="",
            upper_headers=True):
        '''
        args:
            data: list of dicts. Each dict represents a row, where the key is the
                  column name, and the value is the...value

            column_names: list of str. The columns of data to show (and the order
                          in which they are shown)

            title: str. if provided, will be printed above the table

            footer: str. if provided, will be printed below the table

            upper_headers: bool. If True, will automatically uppercase the column
                           header names
        '''
        self.data = data
        self.column_names = column_names
        self.title = title
        self.footer = footer
        self.uppper_headers = upper_headers

    def make_table_str(self):
        """Create and return a final table string that is suitable to
        print/log.

        This is achieved by creating a list of items for each column in the table.
        Once all column lists have been created, they are then joined via a constant
        column space character(s) - self.column_spacer. The rows that are created
        from the columns are then prefixed with given title (self.title) and suffixed
        with the given footer (self.footer)
        """
        column_strs = {}
        for column_name in self.column_names:
            column_strs[column_name] = self.make_column_strs(
                column_name, self.data)

        rows = []
        for row_idx in range(
                len(self.data) + 1):  # add 1 to account for header row
            row_data = []
            for column_name in self.column_names:
                row_data.append(column_strs[column_name][row_idx])
            rows.append(self.column_spacer.join(row_data))

        rows.insert(0, self.get_title())
        rows.append(self.get_footer())
        return self.row_spacer.join(rows)

    def make_column_strs(self, column_name, data):
        """Return a two dimensial list (list of lists), where the inner lists
        repersent a column of data."""
        column_header = self.modify_header(column_name)

        column_cells = []
        for row_dict in data:
            cell_data = row_dict.get(column_name, "")
            cell_data = self.modify_cell(column_name, cell_data)
            column_cells.append(str(cell_data))

        column_data = [column_header] + column_cells
        column_width = len(max(column_data, key=len))

        column_strs = []
        for cell_str in column_data:
            column_strs.append(cell_str.ljust(column_width))

        return column_strs

    def modify_header(self, column_name):
        """
        Modify and return the given column name.

        This provides an opportunity to adjust what the header should
        consist of.
        """
        header_modifier = self.header_modifiers.get(column_name)
        if header_modifier:
            column_name = header_modifier(column_name)
        return column_name.upper() if self.uppper_headers else column_name

    def modify_cell(self, column_name, cell_data):
        """Modify and return the given cell data of the given column name.

        This provides an opportunity to adjust what the header should
        consist of.
        """
        cell_modifier = self.cell_modifiers.get(column_name)
        if cell_modifier:
            cell_data = cell_modifier(cell_data)
        return cell_data

    def get_title(self):
        return self.title

    def get_footer(self):
        return self.footer


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
