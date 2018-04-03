"""frame range section in the UI."""

import hou
from conductor.houdini.hda import takes, uistate
from conductor.houdini.lib.sequence import Sequence

# Specify that Expressions are Python
XP = hou.exprLanguage.Python


def _replace_with_input_expression(parm, input_path):
    """Write expression based on equivalent parm on input node."""
    parm.deleteAllKeyframes()
    parm.setExpression('ch("%s")' % input_path, XP, True)


def _set_to_input(node, rop):
    """Give all channels an expression to link the input node.

    If rop doesn't actually have f1, f2, f3 then we cant
    link, so throw an error.
    """

    if not rop:
        return
    rop_path = rop.path()

    for channel in ['1', '2', '3']:
        if not rop.parm("f%s" % channel):
            raise TypeError(
                """The selected ROP %s has no frame range parameter. 
                Please select or create an output Rop with start, end, and step""" % rop_path)
        _replace_with_input_expression(
            node.parm('fs%s' % channel), '%s/f%s' % (rop_path, channel))


def _set_to_scene(node):
    """Give all channels an expression to link the global settings."""
    node.parm('fs1').setExpression(
        'hou.playbar.timelineRange()[0]', XP, True)
    node.parm('fs2').setExpression(
        'hou.playbar.timelineRange()[1]', XP, True)
    node.parm('fs3').setExpression(
        'hou.playbar.frameIncrement()', XP, True)


def custom_frame_sequence(node):
    """Generate Sequence from value in custom_range parm."""
    spec = node.parm("custom_range").eval()
    clump_size = node.parm("clump_size").eval()
    try:
        return Sequence.create(spec, clump_size=clump_size)
    except (ValueError, TypeError):
        return None



def range_frame_sequence(node):
    """Generate Sequence from value in standard range parm."""
    clump_size = node.parm("clump_size").eval()
    start, end, step = [
        node.parm(parm).eval() for parm in ['fs1', 'fs2', 'fs3']
    ]
    try:
        return Sequence.create(start, end, step, clump_size=clump_size)
    except ValueError:
        return None


def scout_frame_sequence(node):
    """Generate Sequence from value in scout_frames parm."""
    spec = node.parm("scout_frames").eval()
    try:
        return Sequence.create(spec)
    except ValueError:
        return None


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
    sequence.
    """
    main_seq = main_frame_sequence(node)
    if main_seq and node.parm("do_scout").eval():
        scout_seq = scout_frame_sequence(node)
        if scout_seq:
            return main_seq.intersection(scout_seq)
    return None


def _update_sequence_stats(node):
    """Generate frame stats message.

    Especially useful to know the frame count when frame
    spec is set to custom. Additionally, if scout frames are
    set, display the frame info as the num_scout_frames /
    num_frames. The only scout frames counted are those that
    intersect the set of total frames. If we happen to be in
    a different take, then the user has enabled frames or
    clumps or something, and this will affect the
    frame_stats, so they have to be unlocked.
    """
    takes.enable_for_current(node, "frame_stats")

    main_seq = main_frame_sequence(node)
    if main_seq:
        num_frames = len(main_seq)
    else:
        node.parm("frame_stats1").set("-")
        node.parm("frame_stats2").set("-")
        return

    frame_info = "%d Frames" % num_frames
    scout_seq = resolved_scout_sequence(node)
    if scout_seq:
        frame_info = "%d/%d Frames" % (len(scout_seq), num_frames)

    node.parm("frame_stats1").set(frame_info)
    clumps = main_seq.clump_count()
    node.parm("frame_stats2").set("%d Clumps" % clumps)


def validate_custom_range(node, **_):
    """Set valid tickmark for custom range spec.

    A custom range is valid when it is a comma separated
    list of arithmetic progressions. These can can be
    formatted as single numbers or ranges with a hyphen and
    optionally a step value delimited by an x. Example,
    1,7,10-20,30-60x3,1001, Spaces and trailing commas are
    allowed, but not letters or other non numeric
    characters.
    """
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
    """Set the appropriate expressions in frames UI.

    If user selected custom, just validate the input,
    otherwise make sure the expressions are hooked up to the
    input node, or if it doesn't exist, to the scene
    settings
    """
    rop = hou.node(node.parm('source').evalAsString())
    if node.parm("use_custom").eval():
        validate_custom_range(node)
    elif rop:
        _set_to_input(node, rop)
    else:
        _set_to_scene(node)
    _update_sequence_stats(node)


def on_frame_range_changed(node, **_):
    """When frame range changes, update stats."""
    _update_sequence_stats(node)


def on_clump_size_changed(node, **_):
    """When clump size changes, update stats."""
    _update_sequence_stats(node)


def best_clump_size(node, **_):
    """Adjust the clumpsize based on best distribution.

    If for example there are 120 frames and clump size is
    100, then 2 clumps are needed, so better to adjust clump
    size to 60
    """
    main_seq = main_frame_sequence(node)
    node.parm("clump_size").set(main_seq.best_clump_size())
    _update_sequence_stats(node)


def on_do_scout_changed(node, **_):
    """Update stats when scout_frames toggle on or off."""
    _update_sequence_stats(node)
