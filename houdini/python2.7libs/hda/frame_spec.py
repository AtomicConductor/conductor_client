"""Deal with various ways of specifying frame range."""

import math
import re
import hou
import render_source

# Catch a frame number
NUMBER_RE = re.compile(r"^(\d+)$")
# Catch a frame range with optional step
RANGE_RE = re.compile(r"^(?:(\d+)-(\d+)(?:x(\d+))?)+$")
# Specify that Expressions are Python
XP = hou.exprLanguage.Python


def _clamp(low, val, high):
    """Restrict a value."""
    return sorted((low, val, high))[1]


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


def _to_xrange(tup):
    """Generate a valid xrange from 3 frame spec numbers.

    Numbers may be strings, start may be after end, step may
    be None. We add 1 to the end because when a user
    specifies the end val she expects it to be inclusive.

    """
    start, end, step = tup
    if not step:
        step = 1
    start = int(start)
    end = int(end)
    step = int(step)
    if start > end:
        start, end = end, start
    return xrange(start, (end + 1), step)


def _validate_irregular_frame_spec(spec):
    """Irregular range spec must be reducible to a list of frames.

    Valid irregular range spec consists of either numbers or
    ranges separated by commas. Ranges can have an optional
    step value indicated by 'x'. Example valid custom range
    spec: "120, 5, 26-76,19-23x4, 1000-2000, 3,9," Also
    strips leading/trailing commas from input spec and
    returns it along with a bool (valid)

    """

    value = spec.strip(',')
    valid = bool(value)
    for part in [x.strip() for x in value.split(',')]:
        if not (NUMBER_RE.match(part) or RANGE_RE.match(part)):
            valid = False
            break
    return (valid, value)


def _irregular_frame_set(spec):
    """Set of frames from a string spec.

    Given an irregular frame spec, such as that in custom
    range or scout frames, return a set containing those
    frames.

    """
    result = set()
    val = spec.strip(',')
    for part in [x.strip() for x in val.split(',')]:
        number_matches = NUMBER_RE.match(part)
        range_matches = RANGE_RE.match(part)
        if number_matches:
            vals = number_matches.groups()
            result = result.union([int(vals[0])])
        elif range_matches:
            tup = _to_xrange(range_matches.groups())
            result = result.union(tup)
    return result


def custom_frame_set(node):
    """Generate set from value in custom_range parm."""
    spec = node.parm("custom_range").eval()
    return _irregular_frame_set(spec)


def scout_frame_set(node):
    """Generate set from value in scout_frames parm."""
    spec = node.parm("scout_frames").eval()
    return _irregular_frame_set(spec)


def frame_set(node):
    """Generate set containing current chosen frames."""
    if node.parm("range_type").eval() == "custom":
        return custom_frame_set(node) if node.parm(
            "custom_valid").eval() else set()
    return set(_to_xrange([
        node.parm('fs%s' % parm).eval() for parm in ['1', '2', '3']
    ]))


def _update_frames_stats(node):
    """Generate frame stats message.

    Especially useful to know the frame count when frame
    spec is set to custom. Additionally, if scout frames are
    set, display the frame info as the num_scout_frames /
    num_frames. The only scout frames counted are those that
    intersect the set of total frames.

    """
    main_set = frame_set(node)
    scout_set = scout_frame_set(node)

    num_frames = len(main_set)

    if not num_frames:
        node.parm("frame_stats1").set("-")
        node.parm("frame_stats2").set("-")
        return

    frame_info = "%d Frames" % num_frames
    if node.parm("do_scout").eval():
        num_scout_frames = len(main_set.intersection(scout_set))
        frame_info = "%d/%d Frames" % (num_scout_frames, num_frames)
    node.parm("frame_stats1").set(frame_info)

    clump_size = node.parm("clump_size").eval()
    clump_size = _clamp(1, clump_size, num_frames)
    clumps = math.ceil(num_frames / float(clump_size))
    node.parm("frame_stats2").set("%d Clumps" % clumps)


def validate_custom_range(node, **_):
    """Set valid tickmark for custom range spec."""
    spec = node.parm("custom_range").eval()
    valid, value = _validate_irregular_frame_spec(spec)

    node.parm("custom_valid").set(valid)
    node.parm("custom_range").set(value)

    _update_frames_stats(node)


def validate_scout_range(node, **_):
    """Set valid tickmark for scout range spec.

    TODO Currently we just validate that the string produces
    ranges, however we should also validate that the numbers
    produced exist in the total frame range because clearly
    scout frames must be a subset of total frames

    """
    spec = node.parm("scout_frames").eval()
    valid, value = _validate_irregular_frame_spec(spec)

    node.parm("scout_valid").set(valid)
    node.parm("scout_frames").set(value)
    _update_frames_stats(node)


def set_type(node, **_):
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

    _update_frames_stats(node)


def set_frame_range(node, **_):
    """When frame range changes, update stats.

    Also update cost estimates, although they are currently
    hidden.

    """

    _update_frames_stats(node)


def set_clump_size(node, **_):
    """When clump size changes, update stats."""
    _update_frames_stats(node)


def best_clump_size(node, **_):
    """Adjust the clumpsize based on best distribution.

    If for example there are 120 frames and clump size is
    100, then 2 clumps are needed, so better to adjust clump
    size to 60

    """
    num_frames = len(frame_set(node))
    if not num_frames:
        return
    clump_size = node.parm("clump_size").eval()
    clump_size = _clamp(1, clump_size, num_frames)

    clumps = math.ceil(num_frames / float(clump_size))
    clump_size = math.ceil(num_frames / float(clumps))
    node.parm("clump_size").set(clump_size)
    _update_frames_stats(node)


def do_scout_changed(node, **_):
    """Update stats when scout_frames toggle on or off."""
    _update_frames_stats(node)
