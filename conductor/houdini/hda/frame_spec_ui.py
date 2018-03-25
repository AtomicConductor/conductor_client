"""Deal with various ways of specifying frame range."""

import hou
from conductor.houdini.hda import driver_ui, takes, uistate
from conductor.houdini.lib.sequence.sequence import Sequence
 

# Specify that Expressions are Python
XP = hou.exprLanguage.Python

def _replace_with_input_expression(parm, input_path):
    """Write expression based on equivalent parm on input node."""
    parm.deleteAllKeyframes()
    parm.setExpression('ch("%s")' % input_path, XP, True)


def _set_input(node, rop):
    """Give all channels an expression to link the input node.

    If no input node, then warn the user and defer to
    explicit for now.

    """
 
    if not rop:
        return
    rop_path = rop.path()
    for parm in ['1', '2', '3']:
        _replace_with_input_expression(
            node.parm('fs%s' % parm), '%s/f%s' % (rop_path, parm))


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


def custom_frame_sequence(node):
    """Generate Sequence from value in custom_range parm."""
    spec = node.parm("custom_range").eval()
    clump_size = node.parm("clump_size").eval()
    if Sequence.is_valid_spec(spec):
        return Sequence.from_spec(spec, clump_size=clump_size)
    return Sequence([])


def range_frame_sequence(node):
    """Generate Sequence from value in standard range parm."""
    clump_size = node.parm("clump_size").eval()
    start, end, step = [
        node.parm('fs%s' % parm).eval() for parm in ['1', '2', '3']
    ]
    return Sequence.from_range(start, end, step=step, clump_size=clump_size)


def scout_frame_sequence(node):
    """Generate Sequence from value in scout_frames parm."""
    spec = node.parm("scout_frames").eval()
    return Sequence.from_spec(spec)


def main_frame_sequence(node):
    """Generate Sequence containing current chosen frames."""
    if node.parm("use_custom").eval():
        return custom_frame_sequence(node)
    return range_frame_sequence(node)


def resolved_scout_sequence(node):
    """The sub-sequence the user intends to render immediately.

    If do_scout is off then returning None indicates all
    frames will be rendered. However, if its on and the set
    of scout frames intersects the main frames, then only
    start those frames. If scout frames does not intersect
    the main frames, then the user intended to scout but
    ended up with no frames. This produces an empty
    sequence. Its up to the calling function to handle the
    difference between None and empty Sequence.

    """
    main_seq = main_frame_sequence(node)
    if not node.parm("do_scout").eval():
        return None
    scout_seq = scout_frame_sequence(node)
    return main_seq.intersection(scout_seq)


def _update_sequence_stats(node):
    """Generate frame stats message.

    Especially useful to know the frame count when frame
    spec is set to custom. Additionally, if scout frames are
    set, display the frame info as the num_scout_frames /
    num_frames. The only scout frames counted are those that
    intersect the set of total frames.

    """
    takes.enable_for_current(node, "frame_stats")
    
    try:
        main_seq = main_frame_sequence(node)
        num_frames = len(main_seq)
    except ValueError:
        num_frames = None

    if not num_frames:
        node.parm("frame_stats1").set("-")
        node.parm("frame_stats2").set("-")
        return

    frame_info = "%d Frames" % num_frames

    try:
        scout_seq = resolved_scout_sequence(node)
    except ValueError:
        scout_seq = None


    if scout_seq is not None:
        frame_info = "%d/%d Frames" % (len(scout_seq), num_frames)

    node.parm("frame_stats1").set(frame_info)
    clumps = main_seq.clump_count()
    node.parm("frame_stats2").set("%d Clumps" % clumps)


def validate_custom_range(node, **_):
    """Set valid tickmark for custom range spec."""
    takes.enable_for_current(node, "custom_valid")
    spec = node.parm("custom_range").eval()
    valid = Sequence.is_valid_spec(spec)
    node.parm("custom_valid").set(valid)

    _update_sequence_stats(node)
    uistate.update_button_state(node)


def validate_scout_range(node, **_):
    """Set valid tickmark for scout range spec.

    TODO Currently we only validate that the spec produces
    valid frames. We should also validate that at least one
    scout frame exist in the main frame range.

    """
    takes.enable_for_current(node, "scout_valid")
    spec = node.parm("scout_frames").eval()
    valid = Sequence.is_valid_spec(spec)
    node.parm("scout_valid").set(valid)
    _update_sequence_stats(node)
 

def set_type(node, **_):
    rop = driver_ui.get_driver_node(node)
    if node.parm("use_custom").eval():
        validate_custom_range(node)
    elif rop:
        _set_input(node, rop)
    else:
        _set_scene(node)
    _update_sequence_stats(node)


def set_frame_range(node, **_):
    """When frame range changes, update stats."""
    _update_sequence_stats(node)


def set_clump_size(node, **_):
    """When clump size changes, update stats."""
    _update_sequence_stats(node)


def best_clump_size(node, **_):
    """Adjust the clumpsize based on best distribution.

    If for example there are 120 frames and clump size is
    100, then 2 clumps are needed, so better to adjust clump
    size to 60

    """
    main_seq = main_frame_sequence(node)
    best_clump_size = main_seq.best_clump_size()
    node.parm("clump_size").set(best_clump_size)
    _update_sequence_stats(node)


def do_scout_changed(node, **_):
    """Update stats when scout_frames toggle on or off."""
    _update_sequence_stats(node)
