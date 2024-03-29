import logging
import os
import re
import sys
import glob

from conductor.lib import exceptions

# Regular expressions for different path expressions that are supported
RX_HASH = r"#+"  # image.####.exr
RX_MAPID = r"_MAPID_"  # image_MAPID_.exr
RX_PERCENT = r"%0\d+d"  # image.%04d.exr
RX_UDIM_MARI = r"<UDIM>"  # image.<UDIM>.exr
RX_UDIM_MUDBOX = r"<UVTILE>"  # image.<UVTILE>.exr
RX_UDIM_VRAY = r"\$\d*U.*\$\d*V"  # image.u$2U_v$2V.exr or image.u$Uv$V.exr, etc
RX_TILE_REF_VRAY  = r"<TileRef>" #  image.<A30>.0001.exr
RX_HOUDINI = r"\$F\d*"  # image.$F.exr
RX_ASTERISK = r"\*+"  # image.*.exr
RX_UDIM_ZBRUSH = r"u<U>_v<V>"  # image.u<U>_v<V>.exr
RX_UDIM_ZBRUSH_F = r"u<U>_v<V>_<f>"  # image.u<U>_v<V>_<f>.exr
RX_FRAME_SEQ = "<f>"  # image.<f>.exr
RX_FRAME_REDSHIFT = '<Frame>'  # image.<Frame>.exr


# List of  regular expressions that a filename may be represented as (in maya, nuke, mari, or listed
# in text file, etc)
# NOTE: the order MATTERS.  The more specific/stricter expressions should be first in the list, while
# the more easily-matched expressions at the end.
PATH_EXPRESSIONS = (
    RX_HASH,
    RX_MAPID,
    RX_PERCENT,
    RX_UDIM_ZBRUSH,
    RX_UDIM_ZBRUSH_F,
    RX_UDIM_MARI,
    RX_FRAME_REDSHIFT,
    RX_UDIM_MUDBOX,
    RX_UDIM_VRAY,
    RX_TILE_REF_VRAY,
    RX_HOUDINI,
    RX_FRAME_SEQ,
    RX_ASTERISK,
)

logger = logging.getLogger(__name__)


def separate_path(path, no_extension=False):
    '''
    Seperate the given path into three pieces:
        1. The directory (if any)
        2. The base filename (mandatory)
        3. The file extension (if any)

    For example, given this path:
        "/animals/fuzzy_cat.jpg"
    return
        "/animals", "fuzzy_cat", ".jpg"

    The path argument may be a full filepath (including the directory) or just
    the name of the file.

    Note that there is no way to know with 100% certainty that if a file name has
    a period in it that the characters that follow that period are the file
    extension. By default, this function will assume that all files
    that are passed into it have a file extension, and the extension is
    identified by the last period in the file.  In cases where a file does not
    have a file extension,  this must be indicated to this function by setting
    the no_extension argument to be True.

    An example that illustrates the issue: A file named "2942_image.10312".
    The "10312" could either represent a frame number or an extension. There
    is no way to know for sure. By default, the function will assume that the
    "10312" is an extension.  Override this behavior by setting the no_extensio
    arg to True.
    '''
    dirpath, filename = os.path.split(path)

    if no_extension:
        basename = filename
        extension = ""
    else:
        basename, extension = os.path.splitext(filename)
    return dirpath, basename, extension


def process_dependencies(paths):
    '''
    For the given lists of dependency paths, return a dictionary where the keys
    are the depenency filepaths and the values are paths, and the values are a
    a string, describing what is wrong with the path (if anything). If the path
    is valid, the value will be None

    '''
    dependencies = {}
    for path in paths:

        try:
            process_upload_filepath(path)
            dependencies[path] = None
        except exceptions.InvalidPathException as e:
            msg = e.message.encode('utf-8')
            logger.debug("%s", msg)
            dependencies[path] = msg

    return dependencies


def process_upload_filepaths(paths):
    '''
    Given the list of paths, process each one, ultimately returning a flattened
    list of all processed paths
    '''
    processed_paths = []
    for path in paths:
        processed_paths.extend(process_upload_filepath(path))

    return processed_paths


def process_upload_filepath(path, strict=True):
    '''
    Process the given path to ensure that the path is valid (exists on disk),
    and return any/all files which the path may represent.
    For example, if the path is a directory or an image sequence, then explicitly
    list and return all files that that path represents/contains.


    strict: bool. When True and the give path does not exist on disk, raise an
                  exception.
                  Note that when this function is given a directory path, and
                  and it finds any broken symlinks within the directory, the


    This function should be able to handle various types of paths:
        1. Directory path
        2. File path
        3. Image sequence path


    Process the path by doing the following:

    1. If the path is  an image sequence notation, "explode" it and return
        each frame's filepath.  This relies on the file
        actually being on disk, as the underlying call is to glob.glob(regex).
        Validate that there is at least one frame on disk for the image sequence.
        There is no 100% reliable way to know how many frames should actually be
        part of the image sequence, but we can at least validate that there is
        a single frame.

    2. If the path is a directory then recursively add all file/dir paths
        contained within it

    3. If the path is a file then ensure that it exists on disk and that it conforms
       to Conductor's expectations.



     '''

    paths = []

    if path:

        # If the path is a file (and it exits)
        if os.path.isfile(path):
            # Condition the path to conform to Conductor's expectations
            filepath = conform_platform_filepath(path)

            # Validate that the path meets all expectations
            error_msg = validate_path(filepath)
            if error_msg:
                logger.warning(error_msg)
                if strict:
                    raise exceptions.InvalidPathException(error_msg)
            paths.append(filepath)

        # If the path is a directory
        elif os.path.isdir(path):
            for filepath in get_files(path, recurse=True):
                # when recursing a directory, don't be strict about whether
                # any of it's enclosed files are "missing" (e.g. broken symlinks)
                paths.extend(process_upload_filepath(filepath, strict=False))

        # If the path is a symlink (which must be broken bc os.path.isfile or
        # os.path.isdir would have been True if it existed)
        elif os.path.islink(path):
            message = "No file(s) found for path: %s" % path
            # If we're being strict, then raise an exception
            if strict:
                raise exceptions.InvalidPathException(message)
            # otherwise warn
            logger.warning(message)

        # If we've gotten here, then we know that that the path string is not a literal file or directory.
        # Therefore attempt to resolve the path string from any any variables/expressions
        else:
            # First, try to resolve any environment variables found in the path.
            path = os.path.expandvars(path)
            if os.path.exists(path):
                paths.extend(process_upload_filepath(path))

            # Lastly, try to resolve any expressions found in the path
            else:
                filepaths = get_files_from_path_expression(path)

                if filepaths:
                    # if there are matching frames/files for the given path  expression (e.g image
                    # sequence), treat each frame as a dependency (adding it to the dependency
                    # dictionary and running it through validation)
                    for filepath in filepaths:
                        paths.extend(process_upload_filepath(filepath))
                else:
                    # if there are no matching frames/files found on disk for the given
                    # path expression(e.g image sequence) and we're being strict,
                    # then raise an exception
                    if not filepaths:
                        message = "No files found for path: %s" % path
                        if strict:
                            raise exceptions.InvalidPathException(message)
                        logger.warning(message)

    return paths


def get_common_dirpath(paths):
    '''
    Find the common directory between all of the filepaths (essentially find the
    lowest common denominator of all of the given paths).  If thers is no
    common directory shared between the paths, return None

    For example, given these three filepaths:
        '/home/cat/names/fred.txt'
        '/home/cat/names/sally.txt
        '/home/cat/games/chase.txt
    return
        '/home/cat'


    Exclude the root symbol ("/" or a lettered drive in the case of windows) as
    a valid common directory.


    '''
    # Using os.path.commonprefix only gets us so far, as it merely matches as
    # many characters as possible, but doesn't ensure those characters clearly end
    # on a directory. For example, given these two paths
    #    r"c:\catfood\rats.txt"
    #    r"c:\catmood\happy.txt"
    # it will return "c:\\cat"  - which is not actually a directory
    #
    # Or worse, given these three directories:
    #    r"c:\catfood\rats.txt"
    #    r"c:\catmood\happy.txt"
    #    r"c:\cat\properties.txt"
    # it will return "c:\\cat", which is a directory, BUT it's not actually a
    # common across thre three paths! Misleading/dangerous!
    output_path = os.path.commonprefix(paths)

    if output_path:
        # if the output "path" ends with a slash, then we know it's actually a
        # directory path, and can return it
        if output_path.endswith(os.sep) and _is_valid_path(output_path):
            return output_path.rstrip(os.sep)  # strip of the trailing path separator

        # Otherwise ask for the directory of the output "path"
        dirpath = os.path.dirname(output_path)

        # IF the directory is NOT considered a root directory (such as "/" or "G:\\"
        # then return it
        if _is_valid_path(dirpath):
            return dirpath


def _is_valid_path(path_str):
    '''
    This is dirty/inaccurate helper function to determine whether the given "path"
    is considered valid. If so, return True.

    If the given path_str is any of the following characters, then it's to be
    considered invalid:

        On linux\mac:
                /
                //
                lettered drive (e.g. x:\)

        On windows:
            \
            \\
            lettered drive (e.g. x:\)

    '''

    if path_str in [os.sep, os.sep + os.sep]:  # This will handle / or // on linux/mac and \ and \\ on windows
        return

    if re.match(r"^[a-zA-Z]:\\$", path_str):  # handle's lettered drives on Windows (e.g. g:\ )
        return

    return True


def get_files(dirpath, recurse=True):
    '''
    Return all files found in the given directory.

    Optionally recurse the directory to also include files that are located
    in subdirectories as well
    '''
    files = []

    if not os.path.isdir(dirpath):
        raise Exception("Directory does not exist: '%s'" % dirpath)

    # If operating recursively, use os.walk to grab sub files
    if recurse:
        for sub_dirpath, _, filenames in os.walk(dirpath):
            for filename in filenames:
                filepath = os.path.join(sub_dirpath, filename)
                files.append(filepath)
    else:
        files = []
        for filename in os.listdir(dirpath):
            if os.path.isfile(os.path.join(dirpath, filename)):
                files.append(os.path.join(dirpath, filename))

    return files


def conform_platform_filepath(filepath):
    '''
    For the given path, ensure that the path conforms to the standards that
    Conductor expects. Each platform  may potentially have different rules
    that it follows in order to achieve this.
    '''
    platform = sys.platform

    # If the platform is windows, then run specific Windows rules
    if platform.startswith('win'):
        filepath = conform_win_path(filepath)

    return filepath


def conform_win_path(filepath):
    '''
    For the given filepath, resolve any environment variables in the path
    and convert all backlashes to forward slashes
    '''
    exp_file = os.path.abspath(os.path.expandvars(filepath))
    return os.path.normpath(exp_file).replace('\\', "/")


def validate_path(filepath):
    '''
    Validate that the given filepath:
        1. Does not contain colons.  This is docker path limitation
        2. Starts with a "/".  Otherwise the path cannot be mounted in a linux filesystem

    If the filepath is valid, return None. Otherwise return a message that describes
    why the filepath is invalid

    '''
    # Strip the lettered drive portion of the filepath (if there is one).
    # This is only going to affect a path with a lettered drive on Windows filesystem
    filepath = os.path.splitdrive(filepath)[-1]

    # Validate against any forbidden characters
    forbidden_chars = (":",)
    for char in forbidden_chars:
        if char in filepath:
            return "Forbidden character %r found in filepath: %r" % (char, filepath)

    # Ensure filepath begins with a slash
    if not filepath.startswith("/"):
        return "Filepath does not begin with expected %r. Got %r" % ("/", filepath)


def quote_path(filepath):
    '''
    Wrap the given filepath in double quotes and escape its content.
    '''
    return '"%s"' % filepath.replace('"', '\\"')


def get_files_from_path_expression(path_expression):
    '''
    Given a path expression (such as an image sequence path), seek out all files
    that are part of that path expression (e.g all of the files that are part
    of that image sequence) and return a list of their explicit paths.
    This function relies on what is actually on disk, so only files that are
    found on disk will be returned. If no files are found, return an empty list.

    Supports a variety of path expressions. Here are a few examples:
        "image.####.exr"   # Hash syntax
        "image.####"       # no extension  - if there is no extension for the file then that must be specified by the no_extension argument
        "image.%04d.exr"   # printf format
        "image<UDIM>.exr   # Udim
        "image.$F.exr      # Houdini

    In addition to matching against the file name/root, this function also matches expressions
    found against the directory name/path, e.g.
        /data/shot-###/image.exr
        /data/shot-###/image.####.exr
        /data/shot-###/image.%04d.exr
        /data/shot-###/camera-$F/image.%04d.exr
    '''

    logger.debug("Evaluating path expression: %s", path_expression)
    # Cycle through all regexes and replace each match with a * so that we can glob file system.
    # Note that a single path expression may contain more than one expression, as well as more than
    # one expression format (e.g. containing both  #### and %04d).
    rxs = get_rx_matches(path_expression, PATH_EXPRESSIONS)
    glob_path = path_expression
    for rx in rxs:
        logger.debug("Matched path regular expression: %s", rx)
        glob_path = re.sub(rx, "*", glob_path, flags=re.I)

    logger.debug("glob_path: %r", glob_path)
    return glob.glob(glob_path)


def get_rx_matches(path_expression, expressions, limit=0):
    '''
    Loop through the given list of expressions (regexes), and return those that match the given
    path_expression.  If a limit is provided, return the first n expressions that match.
    '''
    matches = []
    for rx in expressions:
        if re.findall(rx, path_expression, flags=re.I):
            matches.append(rx)
            if limit and len(matches) == limit:
                break
    return matches


def create_file(filepath, mode=0660):
    '''
    Create an empty file with the given permissions (octal)
    '''
    umask_original = os.umask(0)
    try:
        handle = os.fdopen(os.open(filepath, os.O_WRONLY | os.O_CREAT, mode), 'w')
    finally:
        os.umask(umask_original)
    handle.write("")
    handle.close()


def get_tx_paths(filepaths, existing_only=False):
    '''
    Return the tx filepaths for the given filepaths
    '''
    return [get_tx_path(path, existing_only=existing_only) for path in filepaths]


def get_tx_path(filepath, existing_only=False):
    '''
    For the given filepath, construct a parallel *.tx filepath residing in the same
    directory (same name, different extension).
    If existing_only is True, only return the tx filepath if it exists on disk,
    otherwise return an empty string.
    '''
    filepath_base, _ = os.path.splitext(filepath)
    tx_filepath = filepath_base + ".tx"
    if existing_only and not os.path.isfile(tx_filepath):
        return ""
    return tx_filepath


def strip_drive_letter(filepath):
    '''
    If the given filepath has a drive letter, remove it and return the rest of
    the path

        C:\cat.txt         -->    \cat.txt
        Z:\cat.txt         -->    \cat.txt
        c:/cat.txt         -->    /cat.txt
        z:/cat.txt         -->    /cat.txt
        //cat.txt          -->    //cat.txt
        \cat.txt           -->    \cat.txt
        \\cat\c:\dog.txt   -->    \\cat\c:\dog.txt
        /cat/c:/dog.txt    -->    /cat/c:/dog.txt
        c:\cat\z:\dog.txt  -->    \cat\z:\dog.txt

    Note that os.path.splitdrive should not be used (anymore), due to a change
    in behavior that was implemented somewhere between python 2.7.6 vs 2.7.11
    '''
    rx_drive = r'^[a-z]:'
    return re.sub(rx_drive, "", filepath, flags=re.I)
