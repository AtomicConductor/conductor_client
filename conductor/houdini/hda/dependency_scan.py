"""Get a list of all files that are needed to run a job.

Attributes:     UDIM_RE (Regex): Find <udim> and related
tokens in filenames so they can be globbed.

fetch: get a list of dependencies required for the submission.
"""
import glob
import os
import re

import hou
from conductor.houdini.hda import types

UDIM_RE = re.compile(r"<udim>|<u>|<v>|<U>|<V>|<u2>|<v2>|<U2>|<V2>")


def _file_exists(filename):
    """Does it exist and is it a file?"""
    if not filename:
        return False
    try:
        hou.findFile(filename)
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


def _exists(fn):
    return _file_exists(fn) or _directory_exists(fn)


def _remove_redundant_entries(entries):
    """Remove file entries where containing directory is an entry.

    Given a list containing both /u/fred/myfile and /u/fred,
    remove /u/fred/myfile as it's not necessary. By sorting
    the entries first on depth, then a secondary sort on
    name length reversed, we can move through the list
    linearly, testing previously seen directories with
    startswith(), as opposed to climbing up the path with
    dirname() in a loop. The secondary sort criteria
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
    """Some parameters should not be be evaluated for dependencies.

    Currently we ignore parms on other job or submitter
    nodes. We also ignore the output directory.
    """
    other_node = parm.node()
    if not (types.is_job_node(other_node) or
            types.is_submitter_node(other_node)):
        return True
    # at this stage we know the other node is a job or submitter.
    # If it is not this node we can ignore it
    if other_node != node:
        return False
    # now we know the other node is this node.
    # We want the parm, unless its the output directory,
    # because the out directory should be automatically
    # created when by the render process and the local out
    # directory may already contain a ton of renders.
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




def _flag_parm(parm, subsequence):
    """Add flags to the parm so we know how to process it.

    Run heuristics to determine if parm value varies over time
    and/or needs globbing later in _get_files(). 

    Subsequence is a small set of frames at which we evaluate
    the parm to see if its changing. If subsequence is None,
    that means we are not optimizing by sampling, and
    therefore just set the flag to varying, which means we
    will evaluate every frame.

    If the evaluated parm is empty, then possibly the variable
    was mal-formed or the field is empty, so we return None.
    Its important not to return a valid but empty parm
    because later we may do abspath and that could resolve to
    the home directory or worse.
    """

    result = {"parm": parm, "varying": False, "needs_glob": False}

    if subsequence:
        val = parm.evalAtFrame(subsequence.start)
        if not val:
            return

        raw = parm.unexpandedString()
        if val != raw:
            # It can be expanded so it may be varying over time.
            # Therefore, compare some sample frames.
            for i in subsequence:
                nextval = parm.evalAtFrame(i)
                if val != nextval:
                    result["varying"] = True
                    break
                val = nextval
    else:
        result["varying"] = True

    result["needs_glob"] = bool(UDIM_RE.search(parm.eval()))
    return result


def _get_files(parm, sequence):
    """Resolve filenames from parms.

    We have previously run some heuristic _flag_parm and
    marked each parm to know whether it needs to be globbed
    or if it varies over time.
    """
    files = []
    if parm["varying"] and parm["needs_glob"]:
        for frame in sequence:
            val = parm["parm"].evalAtFrame(frame)
            val = UDIM_RE.sub('*', val)
            val = os.path.abspath(val)
            files += glob.glob(val)
        return files

    if parm["varying"]:
        for frame in sequence:
            fn = os.path.abspath(parm["parm"].evalAtFrame(frame)) 
            if _exists(fn):
                files.append(fn)
        return files

    if parm["needs_glob"]:
        val = parm["parm"].eval()
        val = UDIM_RE.sub('*', val)
        val = os.path.abspath(val)
        files += glob.glob(val)
        return files

    fn = val = os.path.abspath(parm["parm"].eval())
    if _exists(fn):
        return [fn]


def fetch(node, sequence, samples=None):

    result = set()
    file_refs_parms = _ref_parms(node)
    subsequence = samples and sequence.subsample(samples)

    parms = [_flag_parm(p, subsequence) for p in file_refs_parms]

    for parm in parms:
        if parm:
            files = _get_files(parm, sequence) or []
            for f in files:
                result.add(os.path.normpath(f))

    result = _remove_redundant_entries(result)

    return sorted(result)
