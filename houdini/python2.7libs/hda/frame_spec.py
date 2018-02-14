
"""Deal with various ways of specifying frame range.

Attributes:
* NUMBER_RE: (Regex) Catch a frame number
* RANGE_RE: (Regex) Catch a frame range with optional step
* XP (Enum): Specify that Expressions are Python

"""

import re
import hou
import render_source
import stats
from math import ceil

NUMBER_RE = re.compile(r"^(\d+)$")
RANGE_RE = re.compile(r"^(?:(\d+)-(\d+)(?:x(\d+))?)+$")
XP = hou.exprLanguage.Python


def _replace_with_value(parm, value=None):
    """Overwrite a controlled parm with its evaluated value or a given
    value."""
    val = value or parm.eval()
    parm.deleteAllKeyframes()
    parm.set(val)


def _replace_with_input_expression(parm, input_path):
    """Write expression based on equivalent parm on input node."""
    parm.deleteAllKeyframes()
    parm.setExpression('ch("%s")' % input_path, XP, True)


def _set_explicit(node):
    """Remove expressions on all channels and replace with evaluated."""
    for parm in ['1', '2', '3']:
        _replace_with_value(node.parm('fs%s' % parm))


def _set_input(node):
    """Give all channels an expression to link the input node.

    If no input node, then warn the user and defer to
    explicit for now.

    """
    input_node = render_source.get_render_node(node)
    if not input_node:
        hou.ui.displayMessage(
            title='Missing input node',
            text="Please connect a source node and try again.",
            severity=hou.severityType.ImportantMessage)
        node.parm("range_type").set('explicit')
        _set_explicit(node)
        return
    input_node_path = input_node.path()
    for parm in ['1', '2', '3']:
        _replace_with_input_expression(
            node.parm('fs%s' % parm), '%s/f%s' % (input_node_path, parm))


def _set_scene(node):
    """Give all channels an expression to link the scene settings."""
    node.parm('fs1').setExpression(
        'hou.playbar.timelineRange()[0]', XP, True)
    node.parm('fs2').setExpression(
        'hou.playbar.timelineRange()[1]', XP, True)
    node.parm('fs3').setExpression(
        'hou.playbar.frameIncrement()', XP, True)


def _set_custom(node):
    """When switching to custom, just validate existing input."""
    validate_custom_range(node)
    stats.update_estimates(node)


def _to_xrange(tup):
    """Generate a valid xrange from 3 frame spec numbers.

    Numbers may be strings, start may be after end, step may
    be None. We add 1 to the end because when a user
    specifies the end val she expects it to be inclusive.

    """
    start, end, step = tup
    if (step is None or step == 0):
        step = 1
    start = int(start)
    end = int(end)
    step = int(step)
    if start > end:
        start, end = end, start
    return xrange(start, (end + 1), step)


def _custom_frame_set(node):
    """Generate an exclusive set of frames.

    Input is from the string in custom range parm. It is
    assumed to be valid, but will quietly return empty set
    if not.

    """
    s = set()
    val = node.parm("custom_range").eval().strip(',')
    for part in [x.strip() for x in val.split(',')]:
        number_matches = NUMBER_RE.match(part)
        range_matches = RANGE_RE.match(part)
        if number_matches:
            vals = number_matches.groups()
            s = s.union([int(vals[0])])
        elif range_matches:
            tup = _to_xrange(range_matches.groups())
            s = s.union(tup)
    return s


def frame_count(node, **kw):
    """Count the frames for any range input type."""
    if node.parm("range_type").eval() == "custom":
        return len(_custom_frame_set(node)) if node.parm(
            "custom_valid").eval() else 0
    return len(_to_xrange([
        node.parm('fs%s' % parm).eval() for parm in ['1', '2', '3']
    ]))


def validate_custom_range(node, **kw):
    """Custom range spec must be reducible to a list of frames.

    Valid custom range spec consists of either numbers or
    ranges separated by commas. Ranges can have an optional
    step value indicated by 'x'. Example valid custom range
    spec: "120, 5, 26-76,19-23x4, 1000-2000, 3,9," Also
    strips leading/trailing commas from input

    """
    result = True
    val = node.parm("custom_range").eval().strip(',')
    if not bool(val):
        result = False
    for part in [x.strip() for x in val.split(',')]:
        if not (NUMBER_RE.match(part) or RANGE_RE.match(part)):
            result = False
            break
    node.parm("custom_valid").set(result)
    node.parm("custom_range").set(val)

    stats.update_estimates(node)
    stats.update_frames_stats(node)


def set_type(node, **kw):
    """Switch between different types of frame specification.

    * Explicit: make inputs settable directly
    * Input: link to frame range set in render node
    * Scene: link to frame range set in scene
    * Custom: give a range spec

    """
    funcs = {
        "explicit": _set_explicit,
        "input": _set_input,
        "scene": _set_scene,
        "custom": _set_custom
    }
    func = node.parm("range_type").eval()
    funcs[func](node)
    stats.update_estimates(node)
    stats.update_frames_stats(node)


def set_frame_range(node, **kw):
    """When frame range changes, update stats.

    Also update cost estimates, although they are currently
    hidden.

    """
    stats.update_estimates(node)
    stats.update_frames_stats(node)


def set_clump_size(node, **kw):
    """When clump size changes, update stats."""
    stats.update_frames_stats(node)


def best_clump_size(node, **kw):
    """Adjust the clumpsize based on best distribution.

    If for example there are 120 frames and clump size is
    100, 2 clumps are needed, so a better distribution will
    be to adjust clump size to 60

    """
    num_frames = frame_count(node)
    if not num_frames:
        return
    clump_size = node.parm("clump_size").eval()
    if clump_size < 1:
        clump_size = 1
    elif clump_size > num_frames:
        clump_size = num_frames

    clumps = ceil(num_frames / float(clump_size))
    clump_size = ceil(num_frames / float(clumps))
    node.parm("clump_size").set(clump_size)
    stats.update_frames_stats(node)
