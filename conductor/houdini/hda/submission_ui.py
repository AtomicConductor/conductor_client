import hou
import re
import os
# Catch a timestamp of the form 2018_02_27_10_59_47 with optional
# underscore delimiters at the start and/or end of a string
TIMESTAMP_RE = re.compile(r"^[\d]{4}(_[\d]{2}){5}_*|_*[\d]{4}(_[\d]{2}){5}$")


def stripped_hip():
    """Strip off the extension and timestamp from start or end."""
    no_ext = re.sub('\.hip$', '', hou.hipFile.basename())
    return re.sub(TIMESTAMP_RE, '', no_ext)


def _construct_scene_name(timestamp=None):
    path =  hou.hipFile.path()
    if not timestamp:
        return path
    stripped = stripped_hip()
    path = os.path.dirname(path)
    if not path:
        path = hou.getenv("JOB")
    return os.path.join(path, "%s_%s.hip" % (stripped, timestamp))


def set_scene_name(node, timestamp="YYYY_MM_DD_hh_mm_ss"):

    ts = None
    if node.parm("use_timestamped_scene").eval():
        ts = timestamp
    result = _construct_scene_name(ts)
    node.parm("scene_file").set(result)
    return result


def toggle_timestamped_scene(node, **kw):
    set_scene_name(node)
 