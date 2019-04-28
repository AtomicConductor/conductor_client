import re

import ix
from conductor.clarisse.scripted_class import frames_ui
from conductor.native.lib.gpath_list import PathList
from conductor.native.lib.sequence import Sequence

RX_HASH = re.compile("#+")
RX_UDIM = re.compile("<UDIM>")
GLOB = 1
SMART = 2


def collect(obj):
    """Collect all upload files.

    Always add any extra uploads the user has chosen. Then do a scan if
    the policy is not None.
    """

    policy = obj.get_attribute("dependency_scan_policy").get_long()

    result = PathList()

    result.add(
        "$CONDUCTOR_LOCATION/conductor/clarisse/scripts")

    result.add(*_get_extra_uploads(obj))

    result.add(*get_scan(obj, policy))

    # tell the list to expand  any "*" or <UDIM> in place
    result.glob()
    return result


def get_scan(obj, policy):
    """Make a dependencyList according to the policy."""
    result = PathList()
    result.add(*_resolve_file_paths(obj, policy))
    result.add(*_get_references(obj, policy))
    return result


def _get_extra_uploads(obj):
    """Get extra uploads from the extra_uploads attribute."""
    extras_attr = obj.get_attribute("extra_uploads")
    paths = ix.api.CoreStringArray()
    extras_attr.get_values(paths)
    return paths


def _resolve_file_paths(obj, policy):
    """Scan for dependencies according to the given policy.

    If policy is not None, first replace all UDIM tags with a "*" so
    they may be globbed. File sequences may be resolved one of 2 ways.
    If policy is GLOB, then hashes in filenames will be replaced by a
    "*" and globbed later. If policy is SMART then for each filename, we
    look at its sequence definition and calculate the frames that will
    be needed for the frame range being rendered.
    """
    result = []
    if not policy:
        return result
    for attr in ix.api.OfAttr.get_path_attrs():
        print "- "* 40
        # print "ATTR NAME",  attr.get_parent_object().get_name(), attr.get_name()
        # print "FLAGS", attr.get_flags_names()
        if attr.get_parent_object().is_disabled():
            continue
        hint = ix.api.OfAttr.get_visual_hint_name(attr.get_visual_hint())
        # we want dependencies, not dependents
        # print "HINT", hint
        if attr.is_private():
            continue
        if hint == "VISUAL_HINT_FILENAME_SAVE":
            continue

        filename = attr.get_string()
        filename = RX_UDIM.sub("*", filename)
        # print "FILENAME", filename
        if RX_HASH.search(filename):
            # print "Filename has hashes", filename
            if policy == SMART:
                # print "Policy is smart!"
                # The intersection of the sequence being rendered, and 
                # sequence defined by this attribute
                main_seq = frames_ui.main_frame_sequence(obj)
                # print "MAIN SEQ", main_seq
                attr_seq = _attribute_sequence(attr, intersector=main_seq)
                # print "ATTR SEQ", attr_seq
                if attr_seq:
                    seq_paths = attr_seq.expand(filename)
                    result += seq_paths
            else:  # policy is GLOB
                # print "Policy is glob!"
                result.append(re.sub(r'(#+)', "*", filename))
        else:
            result.append(filename)
    # print result
    return result


def _get_references(_, policy):
    """Get referenced files from contexts.

    We handle contexts separately because Clarisse has a bug where
    get_path_attrs() doesn't find all the attrs in a series of nested
    references. References do not have any wildcards in their names, so
    no need to do any expansion.
    """
    result = []
    if not policy:
        return result
    contexts = ix.api.OfContextSet()
    ix.application.get_factory().get_root().resolve_all_contexts(contexts)
    for context in contexts:
        if context.is_reference() and not context.is_disabled():
            result.append(context.get_attribute("filename").get_string())
    return result


def _attribute_sequence(attr, **kw):
    """Get the sequence associated with a filename attribute.

    Many attributes have an associated sequence_mode attribute, which
    when set to 1 signifies varying frames, and makes availabel start,
    end, and offset attributes to help specify the sequence.

    If the keyword intersector is given, then work out the intersection
    with it. Why? Because during dependency scanning, we can optimize
    the number of frames to upload if we use only those frames specified
    in the sequence attribute, and intersect them with the frame range
    specified in the job node.
    """
    intersector = kw.get("intersector")

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



    if intersector:
        # If there's a frame offset on the attribute, then we need to 
        # do the intersection in the context of that offset.
        offset = obj.get_attribute("frame_offset").get_long()
        return Sequence.create(start, end, 1).offset(
            offset).intersection(intersector).offset(-offset)

    return Sequence.create(start, end, 1)
