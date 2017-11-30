'''
exceptions module

This module handles all custom exceptions for the Conductor Client Tools
All exceptions should at minimum inherit off of the Exception base class
'''

class BackendDown(Exception):
    '''
    Backend is down
    '''

class BackendError(Exception):
    '''
    Something happened on the backend
    '''

class DownloaderExit(SystemExit):
    '''
    Custom exception to handle (and raise) when the DownloadWorker processes
    should be halted.  This subclasses the SystemExit builtin exception. Raising it
    will exit the process with the given return code.
    '''

class FailDownload(Exception):
    '''
    Custom exception to raise when a download should be failed. This may be due to
    a variety of reasons, such as the remote file not existing, or not having adequate
    permissions for writing to a local disk, etc.
    This exception is used to bypass the retry decorator so that the download is NOT retried.
    '''

class FilePutError(Exception):
    '''
    Something happened during the put
    '''

class InvalidPathException(Exception):
    '''
    A path is invalid
    '''
    pass

class UploaderMissingFile(Exception):
    '''
    A file is missing
    '''

class UploaderFileModified(Exception):
    '''
    Something wrong with a local file
    '''

class UserCanceledError(Exception):
    '''
    Custom Exception to indicate that the user cancelled their action
    '''