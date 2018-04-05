"""Manage the submission UI.

In a job node, the submission UI is a tab.
In a submitter node it is the whole UI.

Attributes:     TIMESTAMP_RE (Regex): Catch a timestamp of
the form 2018_02_27_10_59_47 with optional underscore
delimiters at the start and/or end of a string
"""
import hou
import re
import os

TIMESTAMP_RE = re.compile(r"^[\d]{4}(_[\d]{2}){5}_*|_*[\d]{4}(_[\d]{2}){5}$")


def stripped_hip():
    """Strip off the extension and timestamp from current filename.

    Timestamp is intended to be a safe autosave mechanism,
    so stripping the timestamp is a precaution in case the
    user opened a scene that was autosaved and had the
    timestamp still in the title. It avoids timestamps
    getting added to timestamps.
    """
    no_ext = re.sub('\.hip$', '', hou.hipFile.basename())
    return re.sub(TIMESTAMP_RE, '', no_ext)


def _construct_scene_name(timestamp=None):
    """Make the scene name that will be used for the submission.

    If a timestamp is given it is appended to the basename,
    and then the extension is put back.
    """
    path = hou.hipFile.path()
    if not timestamp:
        return path
    stripped = stripped_hip()
    return os.path.join(os.path.dirname(path), "%s_%s.hip" % (stripped, timestamp))


def set_scene_name(node, timestamp="YYYY_MM_DD_hh_mm_ss"):
    """Set the scene name hint in the UI.

    This really just indicates whether a timestamp will be
    added. In the case when it will, the timestamp itself
    will be either a placeholder or the timestamp of the
    last submission. A new timestamp is generated for each
    new submission.
    """
    ts = timestamp if node.parm("use_timestamped_scene").eval() else None
    result = _construct_scene_name(ts)
    node.parm("scene_file").set(result)
    return result


def on_toggle_timestamped_scene(node, **kw):
    """Callback when use_timestamp is toggled"""
    set_scene_name(node)
