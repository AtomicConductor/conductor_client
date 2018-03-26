"""Get a list of all files that are needed to run a job.

Attributes:     PARAMETRISED_RE (Regex): Find <udim> or $SF
tokens in filenames so they can be globbed.

fetch: get a list of dependencies required for the submission.
"""
import os
import glob
import re
import hou

PARAMETRISED_RE = re.compile("<udim>|\$SF")


def _file_exists(file):
    """Does it exist and is it a file?"""
    if not file:
        return False
    try:
        hou.findFile(file)
        return True
    except hou.OperationFailed:
        return False


def _directory_exists(directory):
    """Does it exist and is it a directory?"""
    if not directory:
        return False
    try:
        hou.findDirectory(directory)
        return True
    except hou.OperationFailed:
        return False


def _remove_redundant_entries(entries):
    """Remove file entries where containing directory is an entry.

    Given a list containing both /u/fred/myfile and /u/fred,
    remove /u/fred/myfile as its not necessary. By sorting
    the entries first on depth, then a secondary sort on
    name length reversed, we can move through the list
    linearly, testing previously seen directories with
    startswith() (as opposed to climbing up the path with
    dirname() in a loop). The secondary sort criteria
    ensures that a regular filename that prefixes another,
    will not be seen until the other longer name has been
    tested. Example, /u/fred/myfile.a.b will be tested
    before /u/fred/myfile.a so myfile.a.b will not be
    erroneously discarded.
    """
    sorted_entries = sorted(
        entries, key=lambda entry: (entry.count(os.sep), -len(entry)))
    valid_entries = []
    for entry in sorted_entries:
        if any(entry.startswith(p) for p in valid_entries):
            continue
        valid_entries.append(entry)
    return valid_entries


def fetch(sequence):
    """Finds all file dependencies in the project.

    The results contain files and directories that exist and
    are referenced at some frame in the given frame range.
    Entries will not be included if a containing directory
    is present.
    """

    refs = hou.fileReferences()
    result = set()

    for frame in sequence:
        for parm, _ in refs:
            if parm:
                path = os.path.abspath(parm.evalAtFrame(frame))
                path = PARAMETRISED_RE.sub('*', path)
                for file in glob.glob(path):
                    if _file_exists(file) or _directory_exists(file):
                        result.add(file)

    result = _remove_redundant_entries(result)

    return result
