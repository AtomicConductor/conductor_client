import os
import re

import ix
from conductor.clarisse.scripted_class import frames_ui, variables
from conductor.native.lib.gpath import GPathError, Path
from conductor.native.lib.gpath_list import PathList
from conductor.native.lib.sequence import Sequence

RX_HASH = re.compile(r"#+")
RX_FRAME = re.compile(r"\$(\d?)F")
RX_FRAME_FORMAT = re.compile(r"\{frame:\d*d}")
RX_UDIM = re.compile(r"<UDIM>")
GLOB = 1
SMART = 2


# Temporarily overcome a no-negative-frames limitation of the Sequence object.
# Will break with negative offsets of more than a hundred thousand.
SEQUENCE_OFFSET_KLUDGE=100000

# auxiliary scripts provided by conductor and required on the backend.
# Currrently only ct_windows_prep.py, removes drive letters on win.
# These will be copied from SCRIPTS_DIRECTORY to the temp dir in
# preparation for uploading.

# Why not upload directly from Conductor's install?
# Because it makes dealing with paths easier. And it just doesn't feel right.

# Why not just store the drive_letter removal stuff ready on the sidecar?
# Because the installation shouldn't know, or try to determine, what OS the
# submission was generated on. It should be given instructions from the client
# and run them.

# Why not replace drive letters locally, at the same time we make refs local
# and and so on?
# Because then the render package would not be runnable on the local machine.
CONDUCTOR_SCRIPTS = ["ct_windows_prep.py"]
CONDUCTOR_TMP_DIR = os.path.join(
    ix.application.get_factory().get_vars().get("CTEMP").get_string(),
    "conductor")


def collect(obj):
    """Collect all upload files.

    Always add any extra uploads the user has chosen. Then do a scan if
    the policy is not None.
    """
    result = PathList()

    policy = obj.get_attribute("dependency_scan_policy").get_long()
    result.add(*_get_conductor_script_paths())
    result.add(*_get_extra_uploads(obj))
    result.add(*get_scan(obj, policy))

    # tell the list to expand  any "*" or <UDIM> in place
    result.glob()

    return result


def _get_conductor_script_paths():
    """Paths where conductor's own scripts will be uploaded from."""
    result = PathList()
    for script in CONDUCTOR_SCRIPTS:
        result.add(os.path.join(CONDUCTOR_TMP_DIR, script))
    return result


def _get_extra_uploads(obj):
    """Get user specified uploads from the extra_uploads attribute."""
    result = PathList()
    extras_attr = obj.get_attribute("extra_uploads")
    paths = ix.api.CoreStringArray()
    extras_attr.get_values(paths)
    result.add(*paths)
    return result


def get_scan(obj, policy):
    """Scan all path attrs for dependencies according to the given policy.

    If policy is not None, first replace all UDIM tags with a "*" so
    they may be globbed. File sequences may be resolved one of 2 ways.
    If policy is GLOB, then hashes in filenames will be replaced by a
    "*" and globbed later. If policy is SMART then for each filename, we
    look at its sequence definition and calculate the frames that will
    be needed for the frame range being rendered.
    """
    result = PathList()

    if not policy:
        return result
    for attr in ix.api.OfAttr.get_path_attrs():
        if _should_ignore(attr):
            continue

        if attr.is_expression_enabled() and attr.is_expression_activated():
            filename = _evaluate_static_expression(attr)
        else:
            filename = attr.get_string()

        if not filename:
            continue

        # always glob for udims.
        filename = RX_UDIM.sub("*", filename)

        if policy == GLOB:
            # replace all frame identifiers with "*" for globbing later
            filename = re.sub((r"(#+|\{frame:\d*d})"), "*", filename)
            result.add(filename)
        else:  # SMART
            filenames = _smart_expand(obj, attr, filename)
            result.add(*filenames)

    return result


def _is_project_reference(attr):
    """Does the attribute reference a clarisse project?

    If so, we don't include it in the depedency scan because ultimately
    it will be made local. Check the extension, because Alembic and
    pixar formats are also possible.
    """
    obj = attr.get_parent_object()
    if obj.get_class_name() == "Generic":
        if obj.get_name() == "__context_options__":
            path = attr.get_string()
            _, ext = os.path.splitext(path)
            if ext == ".project":
                return True
    return False


def _should_ignore(attr):
    """Is the attribute needed.attribute.

    Ignore if private, disabled, output filename, or reference. We don't
    need refs because we make them local on the client.
    """
    if attr.get_parent_object().is_disabled():
        return True
    if attr.is_private():
        return True
    hint = ix.api.OfAttr.get_visual_hint_name(attr.get_visual_hint())
    if hint == "VISUAL_HINT_FILENAME_SAVE":
        return True
    if _is_project_reference(attr):
        return True
    return False


def _evaluate_static_expression(target_attr):
    """Evaluate the static part of the expression.

    Assume expression is in active state, otherwise we wouldn't be here.

    We are doing this because we want literal paths that are needed for
    the upload. The easiest and most reliable way to evaluate variables
    in the expression is to simply use get_string(). However, if we do
    that, it will evaluate time varying variables like $3F for the current 
    frame only.  NOTE, it does not resolve hash placeholders like ###. 
    So to keep the time vaiang varables variable, we replace them with 
    python named format strings like {frame:0nd} where n is the padding.

    $CDIR/bugs_seq/bugs.####.jpg becomes
    /Users/julian/projects/fish/clarisse/bugs_seq/bugs.####.jpg

    $CDIR/bugs_seq/bugs.$4F.jpg becomes
    /Users/julian/projects/fish/clarisse/bugs_seq/bugs.{frame:04d}.jpg

    With these time varying placeholders left intact, we can expand
    using either the SMART scan policy, or a simple GLOB.
    """

    orig_expr = target_attr.get_expression()

    static_expr = re.sub(r'\$(\d?)F', lambda match: "{{frame:0{:d}d}}".format(
        int(match.group(1) or 0)), orig_expr)

    target_attr.set_expression(static_expr)
    result = target_attr.get_string()
    target_attr.set_expression(orig_expr)
    return result


def _smart_expand(obj, attr, filename):
    """Expand filenames when policy is SMART.

    At this point, filenames may have hashes and/or frame_format
    {frame:02d} style placeholders that represent frame ranges.
    """
    result = []
    main_seq = frames_ui.main_frame_sequence(obj)

    sequences = None

    do_resolve_hashes = RX_HASH.search(filename)
    do_resolve_frame_format = RX_FRAME_FORMAT.search(filename)
    # If a filename had both of the above (pretty rare) then
    # we need to expand the hashes first, but also have a record
    # of what frame numbers (in the timeline) relate to what files,
    # because remember that hashes can represent a sequence with an
    # offset. So after the hash expansion is done, go and resolve
    # the corresponding {frame:02d} style placeholders.
    # To this end, the function _attribute_sequence() returns both
    # the Sequence representing the files, and the Sequence
    # representing the render.
    # sequences["attr_sequence"]
    # sequences["render_sequence"]
    if do_resolve_hashes:
        sequences = _attribute_sequence(attr, main_seq)
        if sequences:
            result = sequences["attr_sequence"].expand(filename)
            if do_resolve_frame_format:
                result = sequences["render_sequence"].expand_format(*result)
    elif do_resolve_frame_format:
        # do_resolve_frame_format ONLY for filename
        result = main_seq.expand_format(filename)
    else:
        # There are no hashes (that intersect) or frame_format_expr
        # components in the filename. So just return the filename
        result = [filename]
    return result


def _attribute_sequence(attr, intersector):
    """Get the sequence associated with a filename attribute.

    Many attributes have an associated sequence_mode attribute, which
    when set to 1 signifies varying frames, and makes available start,
    end, and offset attributes to help specify the sequence. Work out
    the intersection with main sequence because during dependency
    scanning, we can optimize the number of frames to upload if we use
    only those frames specified in the sequence attribute, and intersect
    them with the frame range specified in the job node.
    """

    obj = attr.get_parent_object()
    mode_attr = obj.attribute_exists("sequence_mode")
    if not (mode_attr and mode_attr.get_long()):
        ix.log_error("Attribute is not in sequence mode {}")

    global_frame_rate = ix.application.get_prefs(
        ix.api.AppPreferences.MODE_APPLICATION).get_long_value(
            "animation", "frames_per_second")
    attr_frame_rate = obj.get_attribute("frame_rate").get_long()
    if not attr_frame_rate == global_frame_rate:
        ix.log_error(
            "Can't get attribute sequence when global \
            fps is different from fps on the attribute")

    start = obj.get_attribute("start_frame").get_long()
    end = obj.get_attribute("end_frame").get_long()

    # If there's a frame offset on the attribute, then we need to
    # do the intersection in the context of that offset.

    # NOTE: Due to a current limitation in Sequence (no negative frame numbers)
    # we do a temporary fix using SEQUENCE_OFFSET_KLUDGE. The idea is to do all 
    # the calcs 100000 frames in the future. When Sequence is fixed and can use 
    # negative frame numbers, we can revert back to the simpler version which
    # can be found in this commit: 542581247d1f109c5511b066f2e7ff5e86577751

    offset = obj.get_attribute("frame_offset").get_long()

    seq = Sequence.create(start, end, 1).offset(offset+SEQUENCE_OFFSET_KLUDGE)
    seq = seq.intersection(intersector.offset(SEQUENCE_OFFSET_KLUDGE))
 
    if not seq:
        # The attribute doesn't intersect the render frames
        return
    # Make a copy of the sequence while at the render frames
    render_seq = Sequence.create(str(seq)).offset(-SEQUENCE_OFFSET_KLUDGE)

    attr_seq = seq.offset(-(offset+SEQUENCE_OFFSET_KLUDGE))
    
    return {"attr_sequence": attr_seq, "render_sequence": render_seq}
 