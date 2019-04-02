import ix
import re
from conductor.native.lib.dependency_list import DependencyList
from conductor.native.lib.sequence import Sequence
import conductor.lib.file_utils
from conductor.clarisse.scripted_class import frames_ui

RX_HASH = re.compile("#+")
RX_UDIM = re.compile("<UDIM>")


def collect(obj):
    """Collect all upload files.

    Always add any extra uploads the user has chosen. Then do a scan if
    the policy is is not none.

    """

    index = obj.get_attribute("dependency_scan_policy").get_long()
    policy = [None, "GLOB", "SMART"][index]

    result = DependencyList()

    # I think we'll just add the ct_cnode node script regardless
    # or whether it's being used
    # task_att = obj.get_attribute("task_template")
    # parts = task_att.get_string().split(" ")
    # if parts and parts[0] == "ct_cnode":
    result.add(
        "$CONDUCTOR_LOCATION/conductor/clarisse/bin/ct_cnode",
        must_exist=True)

    result.add(*_get_extra_uploads(obj), must_exist=True)

    result.add(*get_scan(obj, policy), must_exist=False)

    # tell the list to expand  any "*" or <UDIM> in place
    result.glob()
    return result


def get_scan(obj, policy):
    """Make a dependencyList according to the policy"""
    result = DependencyList()
    result.add(*_resolve_file_paths(obj, policy), must_exist=False)
    result.add(*_get_references(obj, policy), must_exist=True)
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
    be needed for the frame range we are rendering.
    """
    result = []
    if not policy:
        return result
    for attr in ix.api.OfAttr.get_path_attrs():
        if attr.get_parent_object().is_disabled():
            continue
        hint = ix.api.OfAttr.get_visual_hint_name(attr.get_visual_hint())
        # we want dependencies, not dependents
        if hint == "VISUAL_HINT_FILENAME_SAVE":
            continue

        filename = attr.get_string()
        filename = RX_UDIM.sub("*", filename)

        if RX_HASH.search(filename):
            if policy is "SMART":
                main_seq = frames_ui.main_frame_sequence(obj)
                attr_seq = _attribute_sequence(attr, intersector=main_seq)
                if attr_seq:
                    seq_paths = attr_seq.expand(filename)
                    result += seq_paths
            else:  # policy is "GLOB"
                result.append(re.sub(r'(#+)', "*", filename))
        else:
            result.append(filename)

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
        ix.log_error("Attribute is not a sequence mode")

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
        offset = obj.get_attribute("frame_offset").get_long()
        return Sequence.create(start, end, 1).offset(
            offset).intersection(intersector).offset(-offset)

    return Sequence.create(start, end, 1)
