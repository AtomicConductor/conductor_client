"""
Responds to events in the frames section of the ConductorJob attribute editor.

Many functions in this module rely on the Sequence class. A Sequence is a bit
like a range() but with functions and properties more geared towards distributed
rendering of animation sequences   Please refer to the sequence.py and
sequence_test.py for more info.
"""

import ix
from conductor.native.lib.sequence import Sequence


def handle_use_custom_frames(obj, attr):
    """
    Responds to use_custom_frames changes.

    Args:
        obj (ConductorJob):
        attr (OfAttr): Attribute that changed.
    """
    hide = not attr.get_bool()
    obj.get_attribute("custom_frames").set_hidden(hide)
    update_frame_stats_message(obj)


def handle_use_scout_frames(obj, attr):
    """
    Responds to use_scout_frames changes.
    """
    obj.get_attribute("scout_frames").set_hidden(not attr.get_bool())
    update_frame_stats_message(obj)


def handle_custom_frames(obj, _):
    """
    Responds to custom_frames spec changes.
    """
    update_frame_stats_message(obj)


def handle_scout_frames(obj, _):
    """
    Responds to scout_frames spec changes.
    """
    update_frame_stats_message(obj)


def handle_chunk_size(obj, _):
    """
    Responds to chunk_size changes.
    """
    update_frame_stats_message(obj)


def handle_images(obj, _):
    """
    Responds to images or layers being added, removed, disabled.
    """
    update_frame_stats_message(obj)


def handle_best_chunk_size(obj, _):
    """
    Responds to best_chunk_size button push].
    """
    main_seq = main_frame_sequence(obj)
    obj.get_attribute("chunk_size").set_long(main_seq.best_chunk_size())
    update_frame_stats_message(obj)


def custom_frame_sequence(obj):
    """
    Generates the custom_frames sequence.

    Returns:
        Sequence: A Sequence object that represents the value in custom_frames.
        It may be a comma-separated list of progressions. Example
        1,7,10-20,30-60x3,1001.
    """
    try:

        spec = obj.get_attribute("custom_frames").get_string()
        seq = Sequence.create(
            spec, chunk_size=obj.get_attribute("chunk_size").get_long()
        )
        return seq
    except (ValueError, TypeError):
        return None


def image_range(image):
    """
    Returns the first, last, and step values from sequence attributes of an image or layer.

    Args:
        image (OfObject):  The image/layer item

    Returns:
        tuple: start, end, step
    """
    return (
        image.get_attribute("first_frame").get_long(),
        image.get_attribute("last_frame").get_long(),
        image.get_attribute("frame_step").get_long(),
    )


def _union_sequence(images):
    """
    Computes the Sequence that is the union of frame ranges of all provided
    images.

    Args:
        images (list of OfObject): The images to consider.

    Returns:
        Sequence: The union Sequence.
    """
    if not images:
        return None
    rng = image_range(images[0])
    seq = Sequence.create(*rng)
    for image in images[1:]:
        rng = image_range(image)
        other = Sequence.create(*rng)
        seq = seq.union(other)
    return seq


def range_frame_sequence(obj):
    """
    Generate Sequence from value in the input images along with chunk_size attribute.

    Args:
        obj (ConductorJob): Item whose images attribute to get images from.

    Returns:
        Sequence: Sequence derived from given images.
    """

    images = ix.api.OfObjectArray()
    obj.get_attribute("images").get_values(images)

    seq = _union_sequence(list(images))
    if not seq:
        return None

    seq.chunk_size = obj.get_attribute("chunk_size").get_long()
    return seq


def main_frame_sequence(obj):
    """
    Generates Sequence that represents current settings.

    If using custom frames, then the value in the custom frames attribute are
    used, otherwise calculate the union of image sequences.

    Args:
        obj (ConductorJob): Item whose attribute to get parameters from.

    Returns:
        Sequence: Sequence that will be used for rendering.
    """
    if obj.get_attribute("use_custom_frames").get_bool():
        return custom_frame_sequence(obj)
    return range_frame_sequence(obj)


def scout_frame_sequence(obj):
    """
    Generate Sequence from value in scout_frames attribute.

    Args:
        obj (ConductorJob): Item whose attribute to get parameters from.

    Returns:
        Sequence: Sequence that represents scout frames.
    """
    try:
        spec = obj.get_attribute("scout_frames").get_string()
        return Sequence.create(spec)
    except (ValueError, TypeError):
        return None


def resolved_scout_sequence(obj):
    """
    The sub-sequence the user intends to render immediately.

    Args:
        obj (ConductorJob): Item whose attribute to get parameters from.

    Returns:
        Sequence: If do_scout is off then returning None indicates all frames
        will be
    rendered.

        If do_scout is on and the set of scout frames intersects the
    main frames, then return the intersection.

    If scout frames does not intersect the main frames, then the user intended
    to scout but ended up with no frames. This produces None. If it becomes a
    problem with people inadvertently rendering a whole sequence thhen we can
    implement a warning popup or something.

    """

    main_seq = main_frame_sequence(obj)
    if main_seq and obj.get_attribute("use_scout_frames").get_bool():
        scout_seq = scout_frame_sequence(obj)
        if scout_seq:
            return main_seq.intersection(scout_seq)
    return None


def update_frame_stats_message(obj):
    """
    Constructs an info message outlining the range that will be rendered and
    scouted.

    Args:
        obj (ConductorJob): Item whose attribute to get parameters from.
    """
    info_attr = obj.get_attribute("frames_info")

    main_seq = main_frame_sequence(obj)

    if not main_seq:
        info_attr.set_string("--")
        return

    num_frames = len(main_seq)
    scout_seq = resolved_scout_sequence(obj)
    if scout_seq:
        frame_info = "%d Scout / %d Frames" % (len(scout_seq), num_frames)
    else:
        frame_info = "%d Frames" % num_frames

    chunks = "%d Chunks" % main_seq.chunk_count()

    info_attr.set_string("{} -- {} -- {}".format(frame_info, chunks, main_seq))
