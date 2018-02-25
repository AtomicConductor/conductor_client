"""Deal with various ways of specifying frame range."""

import math
import re
import hou
import render_source
import sequence as sq

# Catch a frame number
NUMBER_RE = re.compile(r"^(\d+)$")
# Catch a frame range with optional step
RANGE_RE = re.compile(r"^(?:(\d+)-(\d+)(?:x(\d+))?)+$")
# Specify that Expressions are Python
XP = hou.exprLanguage.Python


# def _clamp(low, val, high):
#     """Restrict a value."""
#     return sorted((low, val, high))[1]


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


# def _to_xrange(tup):
#     """Generate a valid xrange from 3 frame spec numbers.

#     Numbers may be strings, start may be after end, step may
#     be None. We add 1 to the end because when a user
#     specifies the end val she expects it to be inclusive.

#     """
#     start, end, step = tup
#     if not step:
#         step = 1
#     start = int(start)
#     end = int(end)
#     step = int(step)
#     if start > end:
#         start, end = end, start
#     return xrange(start, (end + 1), step)


# def _irregular_frame_set(spec):
#     """Set of frames from a string spec.

#     Given an irregular frame spec, such as that in custom
#     range or scout frames, return a set containing those
#     frames.

#     """
#     result = set()
#     val = spec.strip(',')
#     for part in [x.strip() for x in val.split(',')]:
#         number_matches = NUMBER_RE.match(part)
#         range_matches = RANGE_RE.match(part)
#         if number_matches:
#             vals = number_matches.groups()
#             result = result.union([int(vals[0])])
#         elif range_matches:
#             tup = _to_xrange(range_matches.groups())
#             result = result.union(tup)
#     return result


def custom_frame_sequence(node):
    """Generate Sequence from value in custom_range parm."""
    spec = node.parm("custom_range").eval()
    clump_size = node.parm("clump_size").eval()
    if sq.Sequence.is_valid_spec(spec):
        return sq.Sequence.from_spec(spec, clump_size=clump_size)
    return sq.Sequence([])

def range_frame_sequence(node):
    """Generate Sequence from value in standard range parm."""
    clump_size = node.parm("clump_size").eval()
    start, end, step = [
        node.parm('fs%s' % parm).eval() for parm in ['1', '2', '3']
    ]
    return  sq.Sequence.from_range(start, end, step=step, clump_size=clump_size)


def scout_frame_sequence(node):
    """Generate Sequence from value in scout_frames parm."""
    spec = node.parm("scout_frames").eval()
    return sq.Sequence.from_spec(spec)


def main_frame_sequence(node):
    """Generate Sequence containing current chosen frames."""
    if node.parm("range_type").eval() == "custom":
        return custom_frame_sequence(node)
    return range_frame_sequence(node)



# def custom_frame_set(node):
#     """Generate set from value in custom_range parm."""
#     spec = node.parm("custom_range").eval()
#     return _irregular_frame_set(spec)


# def scout_frame_set(node):
#     """Generate set from value in scout_frames parm."""
#     spec = node.parm("scout_frames").eval()
#     return _irregular_frame_set(spec)


# def frame_set(node):
#     """Generate set containing current chosen frames."""
#     if node.parm("range_type").eval() == "custom":
#         return custom_frame_set(node) if node.parm(
#             "custom_valid").eval() else set()
#     return set(_to_xrange([
#         node.parm('fs%s' % parm).eval() for parm in ['1', '2', '3']
#     ]))


def _update_frames_stats(node):
    """Generate frame stats message.

    Especially useful to know the frame count when frame
    spec is set to custom. Additionally, if scout frames are
    set, display the frame info as the num_scout_frames /
    num_frames. The only scout frames counted are those that
    intersect the set of total frames.

    """
    main_seq = main_frame_sequence(node)
    scout_seq = scout_frame_sequence(node)

    num_frames = len(main_seq)

    if not num_frames:
        node.parm("frame_stats1").set("-")
        node.parm("frame_stats2").set("-")
        return

    frame_info = "%d Frames" % num_frames
    if node.parm("do_scout").eval():
        num_scout_frames = len(main_seq.intersection(scout_seq))
        if num_scout_frames:
            frame_info = "%d/%d Frames" % (num_scout_frames, num_frames)
    node.parm("frame_stats1").set(frame_info)
 
    clumps = main_seq.clump_count()

    node.parm("frame_stats2").set("%d Clumps" % clumps)


def validate_custom_range(node, **_):
    """Set valid tickmark for custom range spec."""
    spec = node.parm("custom_range").eval()
    value = spec.strip(',')
    valid = sq.Sequence.is_valid_spec(spec)

    node.parm("custom_valid").set(valid)
    node.parm("custom_range").set(value)

    _update_frames_stats(node)


def validate_scout_range(node, **_):
    """Set valid tickmark for scout range spec.

    TODO Currently we only validate that the spec produces
    valid frames. We should also validate that at
    least one scout frame exist in the main
    frame range.
    """
    spec = node.parm("scout_frames").eval()
    value = spec.strip(',')
    valid = sq.Sequence.is_valid_spec(spec)

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
    main_seq = main_frame_sequence(node)
    best_clump_size = main_seq.best_clump_size()
    node.parm("clump_size").set(best_clump_size)
    _update_frames_stats(node)


def do_scout_changed(node, **_):
    """Update stats when scout_frames toggle on or off."""
    _update_frames_stats(node)
