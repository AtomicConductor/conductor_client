import os, re, sys, glob


# Regular expressions for different path expressions that are supported
RX_HASH = r"#+"
RX_PERCENT = r"%0\d+d"
RX_UDIM = r"<udim>"
RX_HOUDINI = r"\$F\d*"
PATH_EXPRESSIONS = [RX_HASH, RX_PERCENT, RX_UDIM, RX_HOUDINI]




# def get_seq_parts(basename, no_extension=False):
#     '''
#     split a given basename (string) into three parts:
#         - The characters before the frames notation
#         - The characters of the frame notation
#         - The characters after the frames notation
#
#     basename: a filename stripped of it's directory path and it's extension, e.g.
#                 "image.####" or
#                 "image.10" or
#                 "image.%0d" or
#                 "image.10.rattlename"
#
#
#     For example, given this basename: "image.####",
#         return "image.", "####", ""
#
#     or given this string: "image.####.rattlesnake",
#         return "image.", "####", ".rattlesnake"
#
#     '''
#     for rx in [RX_HASH, RX_PERCENT]:
#         match = re.match(rx, basename)
#         if match:
#             frame_padding = derive_frame_padding(match.group("frames"), rx)
#             return match.group("pre_frames"), frame_padding, match.group("post_frames")


# def derive_frame_padding(frames_str, rx):
#     '''
#     From a given frames notation, e.g. "%05d" or "###", derive the frame padding
#     count, e.g. 5, or 3 respectively.
#     '''
#     if rx == RX_HASH:
#         return len(frames_str)
#     elif rx == RX_PERCENT:
#         return int(frames_str[1:-1])
#     else:
#         raise Exception("This shouldn't happen")


# def is_image_seq_notation(path_string):
#     '''
#     Return True if the given filepath (string) uses image sequence notation.
#
#     e.g.  if the path string is similar to:
#               "/batman/cape_v001.%04d.jpg" or
#               "/batman/cape_v001.####.jpg"
#           return True
#
#           If the path string is similar to:
#               "/batman/cape_v001.001.jpg" or
#               "/batman/cape_v001_special.jpg"
#           return False
#
#     '''
#     dirpath, basename, extension = separate_path(path_string)
#     return bool(get_seq_parts(basename))


# def is_hash_notation(path_string, no_extension=False):
#     '''
#     Return True if the given filepath (string) uses hash image sequence notation.
#
#     e.g.  if the path string is similar to:
#               "/batman/cape_v001.####.jpg"
#           return True
#
#
#     '''
#     dirpath, basename, extension = separate_path(path_string, no_extension=no_extension)
#     if re.match(RX_HASH, basename, re.IGNORECASE):
#         return True
#
# def get_files_from_hash_string(path_string, no_extension=False):
#     dirpath, basename, extension = separate_path(path_string, no_extension=no_extension)
#     basename = re.sub(RX_HASH, '*', basename, re.IGNORECASE)
#     glob_str = os.path.join(dirpath, basename + extension)
#     return glob_str
#
#
# def is_percent_notation(path_string, no_extension=False):
#     '''
#     Return True if the given filepath (string) uses hash image sequence notation.
#
#     e.g.  if the path string is similar to:
#               "/batman/cape_v001.%04d.jpg" or
#           return True
#
#
#     '''
#     dirpath, basename, extension = separate_path(path_string, no_extension=no_extension)
#     if re.match(RX_PERCENT, basename, re.IGNORECASE):
#         return True
#
# def get_files_from_percent_string(path_string, no_extension=True):
#     dirpath, basename, extension = separate_path(path_string, no_extension=no_extension)
#     basename = re.sub(RX_PERCENT, '*', basename, re.IGNORECASE)
#     glob_str = os.path.join(dirpath, basename + extension)
#     return glob_str
#
#
# def is_udim_notation(path_string, no_extension=False):
#     '''
#     Return True if the given filepath (string) uses a UDIM notation.
#
#
#
#     e.g.  if the path string is similar to:
#               "/batman/cape_v001.<udim>.jpg" or
#           return True
#     '''
#     dirpath, basename, extension = separate_path(path_string, no_extension=no_extension)
#     if re.match(RX_UDIM, basename, re.IGNORECASE):
#         return True
#
#
# def get_files_from_udim_string(udim_string, no_extension=True):
#     dirpath, basename, extension = separate_path(udim_string, no_extension=no_extension)
#     basename = re.sub(RX_UDIM, '*', basename)
#     glob_str = os.path.join(dirpath, basename + extension)
#     return glob_str
#
#
# def is_houdini_frame_notation(path_string, no_extension=False):
#     '''
#     Return True if the given filepath (string) uses a houdini frame notation.
#
#     e.g.  if the path string is similar to:
#               "/batman/cape_v001.F.jpg" or
#           return True
#     '''
#     dirpath, basename, extension = separate_path(path_string, no_extension=no_extension)
#     if re.match(RX_HOUDINI, basename, re.IGNORECASE):
#         return True
#
#
# def get_files_from_houdini_string(path_string, no_extension=True):
#     dirpath, basename, extension = separate_path(path_string, no_extension=no_extension)
#     basename = re.sub(RX_HOUDINI, '*', basename)
#     glob_str = os.path.join(dirpath, basename + extension)
#     return glob_str




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
    For the given lists of dependency paths, return a dictionary where the keys are the depenency filepaths and the values
    are paths, and the values are a bool, indicating whether the dependency path is valid. 
    
    '''
    dependencies = {}
    for path in paths:
        try:
            process_upload_filepath(path)
            dependencies[path] = True
        except:
            dependencies[path] = False

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

def process_upload_filepath(path):
    '''
    Process the given path to ensure that the path is valid (exists on disk), 
    and return any/all files which the path may represent.  
    For example, if the path is a directory or an image sequence, then explicity 
    list and return all files that that path represents/contains.
    
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


    # Skip the path if its empty/None
    if not path:
        return paths

    # If the path is a file
    if os.path.isfile(path):
        # Condition the path to conform to Conductor's expectations
        paths.append(conform_platform_filepath(path))

    # If the path is a directory
    elif os.path.isdir(path):
        for filepath in get_files(path, recurse=True):
            paths.extend(process_upload_filepath(filepath))

    else:
        # If the path is not a file and not a directory then see if it's path exrpess
        filepaths = get_files_from_path_expression(path)

        # if there are no actual frames on disk for the given image
        # sequence then raise an exception
        if not filepaths:
            _, basename, __ = separate_path(path)
            if get_rx_match(basename, PATH_EXPRESSIONS):
                raise Exception("No files found for path expression: %s", path)
            # If the the path isn't an expression (and it's also not a file or
            # a directory, then what the hell is it? raise an Exception
            raise Exception("Path does not exist: %s" % path)


        # Otherwise treat each frame as a dependency (adding it to the
        # dependency dictionary and running it through validation
        else:
            for filepath in filepaths:
                paths.extend(process_upload_filepath(filepath))

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
            return os.path.normpath(output_path)

        # Otherwise ask for the directory of the output "path"
        dirpath = os.path.dirname(output_path)

        # IF the directory is NOT considered a root directory (such as "/" or "G:\\"
        # then return it
        if _is_valid_path(dirpath):
            return os.path.normpath(dirpath)



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

    # If the platform is posixthen run specific posix rules
    else:
        filepath = conform_unix_path(filepath)

    # Regardless of platform, do a check to ensure that absolute paths are being used
    if not filepath.startswith('/'):
        print('All files should be passed in as absolute linux paths!')
        raise IOError('File does not start at root mount "/", %s' % filepath)

    return filepath


def conform_win_path(filepath):
    '''
    For the given filepath, resolve any environment variables in the path
    and convert all backlashes to forward slashes 
    '''
    exp_file = os.path.abspath(os.path.expandvars(filepath))
    return os.path.normpath(exp_file).replace('\\', "/")

def conform_unix_path(filepath):
    '''
    For the given filepath, resolve any environment variables in the path
    and convert all backlashes to forward slashes 
    '''
    exp_file = os.path.abspath(os.path.expandvars(filepath))
    return os.path.normpath(exp_file).replace('\\', "/")



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
        "image<udim>.exr   # Udim
        "image.$F.exr      # Houdini  
    '''
    dirpath, basename, extension = separate_path(path_expression, no_extension=no_extension)

    rx = get_rx_match(basename, PATH_EXPRESSIONS)
    if rx:
        glob_basename = re.sub(rx, "*", basename)
        glob_filepath = os.path.join(dirpath, glob_basename + extension)
        file_pieces = glob_filepath.split("*")
        files_that_match = get_matching_files(glob_filepath, dev)
        return [reconstruct_filename(matched, file_pieces) for matched in files_that_match]
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








#
# PATH_EXPRESSIONS = {RX_HASH: get_files_from_hash_string
#                     RX_PERCENT: get_files_from_percent_string,
#                     RX_UDIM:get_files_from_udim_string,
#                     RX_HOUDINI: get_files_from_houdini_string]
