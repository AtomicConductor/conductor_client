
import os, re, glob


# There can only be one set of hashes in the filename
RX_HASH = r"(?P<pre_frames>[^#]*)(?P<frames>#+)(?P<post_frames>[^#]*)"

# There can only be one set of % signs in the filename TODO: need to check
# for more than the "%" sign from being in pre/post frame section
RX_PERCENT = r"(?P<pre_frames>[^%]*)(?P<frames>%\d+d)(?P<post_frames>[^%]*)"


def get_files_from_seq_string(seq_string, no_extension=False):
    '''
    Given an image sequence filepath, seek out all image files that are part
    of that image sequence and return their explicit paths.  This function relies
    on what is actually on disk, so only frames that exist will be returned.
    
    Supports a variaty of image sequence strings. Here are a few examples:
        "image.5.exr"      #  explicit frame
        "image.####.exr"   # Hash syntax
        "image.####"       # no extension  - if there is no extension for the file then that must be specified by the no_extension argument
        "image_00000.exr"  # underscores
        "image.%04d.exr"   # printf format
    '''
    glob_str = construct_glob_string(seq_string, no_extension=no_extension)
    return glob.glob(glob_str)


def construct_glob_string(seq_string, no_extension=False):
    '''
    From a given image sequence string return a glob search string that will 
    find all files that make-up that image sequence when called.
    
    For example, given this image sequence string:
        'c:\\images\\image.####.exr'
    return this glob string:
        'c:\\images\\image.[0-9][0-9][0-9][0-9].exr'
    '''
    dirpath, basename, extension = separate_path(seq_string, no_extension=no_extension)
    pre, framepadding, post = get_seq_parts(basename, no_extension=no_extension)
    basname_str = "%s%s%s" % (pre, "[0-9]"*framepadding, post)
    glob_str = os.path.join(dirpath, basname_str + extension)
    return glob_str

def get_seq_parts(basename, no_extension=False):
    '''
    split a given basename (string) into three parts:
        - The characters before the frames notation
        - The characters of the frame notation
        - The characters after the frames notation
    
    For example, given this string: "image.####",
        return "image.", "####". "" 
    
    
    basename: a filename stripped of it's directory path and it's extension, e.g.
        "image.####" or 
        "image.10" or
        "image.%0d
         
    '''


    for rx in [RX_HASH, RX_PERCENT]:
        match = re.match(rx, basename)
        if match:
            frame_padding = derive_frame_padding(match.group("frames"), rx)
            return match.group("pre_frames"), frame_padding, match.group("post_frames")

def derive_frame_padding(frames_str, rx):
    '''
    From a given frames notation, e.g. "%05d" or "###", derive the frame padding
    count, e.g. 5, or 3 respectively.
    '''
    if rx == RX_HASH:
        return len(frames_str)
    elif rx == RX_PERCENT:
        return int(frames_str[1:-1])
    else:
        raise Exception("This shouldn't happen")




def is_image_seq_notation(path_string):
    '''
    Return True if the given filepath (string) uses image sequence notation.
    
    e.g.  if the path string is similar to:
              "/batman/cape_v001.%04d.jpg" or
              "/batman/cape_v001.####.jpg"
          return True
          
          If the path string is similar to:
              "/batman/cape_v001.001.jpg" or
              "/batman/cape_v001_special.jpg"
          return False
            
    '''
    dirpath, basename, extension = separate_path(path_string)
    return bool(get_seq_parts(basename))



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
    For the given lists of paths, ensure that:
    
    1. The path exists on disk
    2. The path is normalized
    3. If the path is  an image sequence notation, "explode" it and explicitly add 
        each frame's filepath to the dependency list.  This relies on the file 
        actually being on disk, as the underlying call is to glob.glob(regex).
        Validate that there is at least one frame on disk for the image sequence.
        There is no 100% reliable way to know how many frames should actually be
        part of the image sequence, but we can at least validate that there is 
        a single frame.
        
    4. What if the path is a directory? Upload contents of directory? TODO:
    
    Return a dictionary where the keys are the depenency filepaths and the values
    are bools, indicating whether the path exists or not. 
    
    '''
    dependencies = {}
    for path in paths:
        # Skip any paths that are empty/None value
        if not path:
            continue

        # If the path is an image sequence, then find each image in the image
        # sequence and add it to the dependencies dictionary
        if is_image_seq_notation(path):
            frame_filepaths = get_files_from_seq_string(path)

            # if there are no actual frames on disk for the given image
            # sequence then flag this image sequence as an invalid path.
            if not frame_filepaths:
                dependencies[path] = False

            # Otherwise treat each frame as a dependency (adding it to the
            # dependency dictionary and running it through validation
            else:
                dependencies.update(process_dependencies(frame_filepaths))
            continue

        # Normalize the path
        path = os.path.normpath(path)

        # Add the path to dictionary and indicate whether is exists on disk
        dependencies[path] = os.path.isfile(path)

    return dependencies

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
