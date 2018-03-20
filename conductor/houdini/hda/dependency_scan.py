import os
import glob
import re
import hou

PARAMETRISED_RE = re.compile("<udim>|\$SF")


def _file_exists(file):
    if not file:
        return False
    try:
        hou.findFile(file)
        return True
    except  hou.OperationFailed:
        return False


def _directory_exists(directory):

    if not directory:
        return False
    try:
        hou.findDirectory(directory)
        return True
    except  hou.OperationFailed:
        return False

def _remove_redundant_entries(entries, directories):
    #Remove entries where a containing directory exists
    result = []
    for entry in entries:
        mutable = entry
        found = False
        while mutable != os.sep:
            mutable = os.path.dirname(mutable)
            if mutable in directories:
                found = True
                break
        if not found:
            result.append(entry)
    return result


def fetch(sequence):
    """Finds all file dependencies in the project.

    The results contain files and directories  that exist in
    the frame range, PLUS files in te whitelisted parms. For
    example, the scene file may not exist, but we want to
    show that it is a dependency as it will presumably exist
    when a submission is uploaded.

    """

    refs = hou.fileReferences()
    result = set()
    directories = set()

    whitelist_parms = ["scene_file"]
    for parm, _ in refs:
        if parm and parm.name() in whitelist_parms:
            file = parm.eval()
            if file:
                result.add(file.rstrip(os.sep))

    for frame in sequence:
        for parm, _ in refs:
            if parm:
                path = os.path.abspath(parm.evalAtFrame(frame))
                path =PARAMETRISED_RE.sub('*', path)
                for file in glob.glob(path):
                    if _file_exists(file):
                        result.add(file)
                    elif _directory_exists(file):
                        result.add(file)
                        directories.add(file)
 
    result = _remove_redundant_entries(list(result), list(directories))

    return  result
