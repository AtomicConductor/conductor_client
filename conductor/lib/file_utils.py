import logging
import os
import re
import sys
import glob
import stat



# Regular expressions for different path expressions that are supported
RX_HASH = r"#+"  # image.####.exr
RX_PERCENT = r"%0\d+d"  # image.%04d.exr
RX_UDIM_MARI = r"<UDIM>"  # image.<UDIM>.exr
RX_UDIM_MUDBOX_L = r"<UVTILE>"  # image.<UVTILE>.exr
RX_UDIM_MUDBOX_U = r"<uvtile>"  # image.<uvtile>.exr
RX_UDIM_VRAY_L = r"\$\d*U.*\$\d*V"  # image.u$2U_v$2V.exr or image.u$Uv$V.exr, etc
RX_UDIM_VRAY_U = r"\$\d*v.*\$\d*v"  # image.u$2u_v$2v.exr or image.u$uv$v.exr, etc
RX_HOUDINI = r"\$F\d*"  # image.$F.exr
RX_ASTERISK = r"\*+"  # image.*.exr

# List of  regular expressions that a filename may be represented as (in maya, nuke, mari, or listed in text file, etc)
PATH_EXPRESSIONS = [RX_HASH, RX_PERCENT, RX_UDIM_MARI, RX_UDIM_MUDBOX_L,
                    RX_UDIM_MUDBOX_U, RX_UDIM_VRAY_L, RX_UDIM_VRAY_U, RX_HOUDINI,
                    RX_ASTERISK]

logger = logging.getLogger(__name__)



class InvalidPathException(Exception):
    pass

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
    "10312" is an extension.  Override this behavior by setting the no_extension
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
        except InvalidPathException as e:
            dependencies[path] = str(e)


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
                    raise InvalidPathException(error_msg)
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
                raise InvalidPathException(message)
            # otherwise warn
            logger.warning(message)

        # If the path is not a file and not a directory then see if it's a path expression
        else:
            filepaths = get_files_from_path_expression(path)

            if filepaths:
                # if there are matching frames/files for the given path
                # expression(e.g image sequence), treat each frame as a dependency
                # (adding it to the dependency dictionary and running it through validation)
                for filepath in filepaths:
                    paths.extend(process_upload_filepath(filepath))
            else:
                # if there are no matching frames/files found on disk for the given
                # path expression(e.g image sequence) and we're being strict,
                # then raise an exception
                if not filepaths:
                    message = "No files found for path: %s" % path
                    if strict:
                        raise InvalidPathException(message)
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

    if path_str in [os.sep, os.sep + os.sep] :  # This will handle / or // on linux/mac and \ and \\ on windows
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
    Conductor expects. Each platform  may potententially have different rules 
    that it follows in order to achive this.
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
    
    If the filepath is valid, retur None. Otherwise return a message that describes
    why the filepath is invalid
        
    '''
    # Validate against any forbidden characters
    forbidden_chars = (":",)
    for char in forbidden_chars:
        if char in filepath:
            return "Forbidden character %r found in filepath: %r" % (char, filepath)

    # Ensure filepath begins with a slash
    if not filepath.startswith("/"):
        return "Filepath does not begin with expected %r. Got %r" % ("/", filepath)


def reconstruct_filename(matched, file_pieces):
    full_file_string = ""
    matched = matched.lower()
    for count, piece in enumerate(file_pieces):

        full_file_string += piece

        # If there's more to the file peices add the frame number
        if len(file_pieces) > count + 1:
            dummy_piece = piece.lower()
            frame_val = matched.split(dummy_piece)[1]
            frame_val = frame_val.split(file_pieces[count + 1].lower())[0]
            full_file_string += frame_val

    return full_file_string


def get_files_from_path_expression(path_expression, no_extension=False, dev=False):
    '''
    Given a path expression (such as an image sequence path), seek out all files 
    that are part of that path expression (e.g all of the files that are part
    of that image sequence) and return a list of their explicit paths.  
    This function relies on what is actually on disk, so only files that are 
    found on disk will be returned. If no files are found, return an empty list.
    
    Supports a variaty of path expressions. Here are a few examples:
        "image.####.exr"   # Hash syntax
        "image.####"       # no extension  - if there is no extension for the file then that must be specified by the no_extension argument
        "image.%04d.exr"   # printf format
        "image<UDIM>.exr   # Udim
        "image.$F.exr      # Houdini  
    '''
    dirpath, basename, extension = separate_path(path_expression, no_extension=no_extension)
    logger.debug("Evaluating path expression: %s", path_expression)

    rx = get_rx_match(basename, PATH_EXPRESSIONS)
    if rx:
        logger.debug("Matched path regular expression: %s", rx)
        glob_basename = re.sub(rx, "*", basename)
        glob_filepath = os.path.join(dirpath, glob_basename + extension)
        file_pieces = glob_filepath.split("*")
        files_that_match = get_matching_files(glob_filepath, dev)
        return [reconstruct_filename(matched, file_pieces) for matched in files_that_match]
    logger.debug("Path expression not recognized: %s", path_expression)
    return []


def get_rx_match(path_expression, expressions):
    for rx in expressions:
        if re.findall(rx, path_expression):
            return rx



def get_matching_files(glob_str, dev=False):
    if dev:
        return ['/TMP/foo.bar.0101.testa.101.exr', '/tmp/FOO.bar.0102.testa.102.exr']
    else:
        return glob.glob(glob_str)

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
    For the given filepath, consruct a parallel *.tx filepath residing in the same 
    directory (same name, different extension).
    If existing_only is True, only return the tx filepath if it exists on disk,
    otherwise return an empty string.
    '''
    filepath_base, ext = os.path.splitext(filepath)
    tx_filepath = filepath_base + ".tx"
    if existing_only and not os.path.isfile(tx_filepath):
        return ""
    return tx_filepath



