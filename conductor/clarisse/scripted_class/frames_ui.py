import ix

from conductor.native.lib.sequence import Sequence


def handle_use_custom_frames(obj, attr):
    hide = not attr.get_bool()
    obj.get_attribute("custom_frames").set_hidden(hide)
    obj.get_attribute("progressions").set_hidden(hide)
    update_frame_stats_message(obj)


def handle_use_scout_frames(obj, attr):
    obj.get_attribute("scout_frames").set_hidden(not attr.get_bool())
    update_frame_stats_message(obj)


def handle_custom_frames(obj, _):
    update_frame_stats_message(obj)


def handle_scout_frames(obj, _):
    update_frame_stats_message(obj)


def handle_progressions(obj, _):
    update_frame_stats_message(obj)


def handle_chunk_size(obj, _):
    update_frame_stats_message(obj)


def handle_images(obj, _):
    update_frame_stats_message(obj)


def _chunk_parameters(obj):
    index = int(obj.get_attribute("progressions").get_bool())
    return {
        "size": obj.get_attribute("chunk_size").get_long(),
        "strategy": ["linear", "progressions"][index]
    }


def custom_frame_sequence(obj):
    """Generate Sequence from value in custom_range parm."""
    try:
        print "START TRY custom_frame_sequence"
        spec = obj.get_attribute("custom_frames").get_string()
        print "custom_frame_sequence", spec
        chunk = _chunk_parameters(obj)
        print "chunk", chunk
        seq = Sequence.create(
            spec,
            chunk_size=chunk["size"],
            chunk_strategy=chunk["strategy"]
        )
        return seq
    except (ValueError, TypeError):
        return None


def image_range(image):
    return (
        image.get_attribute("first_frame").get_long(),
        image.get_attribute("last_frame").get_long(),
        image.get_attribute("frame_step").get_long()
    )


def _union_sequence(images):
    # print "LEN IMAGES", len(images)
    if not images:
        return None
    rng = image_range(images[0])
    seq = Sequence.create(*rng)
    # print "remainder len", len(images[1:])
    for image in images[1:]:
        rng = image_range(image)
        other = Sequence.create(*rng)
        seq = seq.union(other)
    return seq


def range_frame_sequence(obj):
    """Generate Sequence from value in the standard range.

    As there may be multiple sources, we make sure all sources have the
    same frame range. If they don't, then we suggest splitting the
    images over multiple jobs. In future we may do this automatically.
    """

    images = ix.api.OfObjectArray()
    obj.get_attribute("images").get_values(images)

    seq = _union_sequence(list(images))
    # print "union_sequence", seq
    if not seq:
        return None

    chunk = _chunk_parameters(obj)

    # print "size", chunk["size"],  type(chunk["size"])
    # print "strategy", chunk["strategy"], type(chunk["strategy"])

    seq.chunk_size = chunk["size"]
    seq.chunk_strategy = chunk["strategy"]
    # print "chunk_size", seq.chunk_size
    # print "chunk_count", seq.chunk_count()
    return seq


def main_frame_sequence(obj):
    """Generate Sequence containing current chosen frames."""
    if obj.get_attribute("use_custom_frames").get_bool():
        return custom_frame_sequence(obj)
    return range_frame_sequence(obj)


def scout_frame_sequence(obj):
    """Generate Sequence from value in scout_frames parm."""
    try:
        spec = obj.get_attribute("scout_frames").get_string()
        return Sequence.create(spec)
    except (ValueError, TypeError):
        return None


def resolved_scout_sequence(obj):
    """The sub-sequence the user intends to render immediately.

    If do_scout is off then returning None indicates all frames will be
    rendered. However, if it is on and the set of scout frames
    intersects the main frames, then only start those frames. If scout
    frames does not intersect the main frames, then the user intended to
    scout but ended up with no frames. This produces an empty sequence.
    """

    main_seq = main_frame_sequence(obj)
    if main_seq and obj.get_attribute("use_scout_frames").get_bool():
        scout_seq = scout_frame_sequence(obj)
        if scout_seq:
            return main_seq.intersection(scout_seq)


def update_frame_stats_message(obj):
    info_attr = obj.get_attribute("frames_info")

    main_seq = main_frame_sequence(obj)

    print "main_seq", main_seq
    if not main_seq:
        info_attr.set_string("--")
        return

    num_frames = len(main_seq)
    scout_seq = resolved_scout_sequence(obj)
    if scout_seq:
        frame_info = "%d/%d Frames" % (len(scout_seq), num_frames)
    else:
        frame_info = "%d Frames" % num_frames

    print "SIZE AND COUNT", main_seq.chunk_size, main_seq.chunk_count()

    chunks = ("%d Chunks" % main_seq.chunk_count())

    info_attr.set_string("{} -- {}".format(frame_info, chunks))
