"""Get a list of all files that are needed to run a job.

Attributes:     PARAMETRISED_RE (Regex): Find <udim> or $SF
tokens in filenames so they can be globbed.

fetch: get a list of dependencies required for the submission.
"""
import os
import glob
import re
import hou

from conductor.houdini.hda import types


PARAMETRISED_RE = re.compile(r"<udim>|\$SF")


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


def _is_wanted(parm, node):
    """Some parameters should not be be evaluated for dependencies."""
    other_node = parm.node()
    if not (types.is_job_node(other_node) or
            types.is_submitter_node(other_node)):
        return True
    # at this stage we know the other node is a job or submitter
    if other_node !=  node:
        return False
    # at this stage we know the other node is this node
    return parm.name() != "output_directory"


def _ref_parms(node):
    """All file parms except those on other job nodes.

    When submitting a job and there are other jobs in the
    scene, we don't want files referenced on those other
    nodes because they are not needed for this job. They are
    likely to be scripts or tools needed to make that other
    job run.
    """
    result = []
    refs = hou.fileReferences()
    for parm, _ in refs:
        if parm and _is_wanted(parm, node):
            result.append(parm)
    return result


def fetch(node, sequence):
    """Finds all file dependencies in the project.

    The results contain files and directories that exist and
    are referenced at some frame in the given frame range.
    Entries will not be included if a containing directory
    is present.
    """

    parms = _ref_parms(node)
    result = set()

    for frame in sequence:
        for parm in parms:
            path = PARAMETRISED_RE.sub(
                '*', os.path.abspath(parm.evalAtFrame(frame)))
            for file in glob.glob(path):
                if file not in result and _file_exists(
                        file) or _directory_exists(file):
                    result.add(file)

    result = _remove_redundant_entries(result)

    return result
