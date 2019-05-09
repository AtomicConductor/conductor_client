import re
import os
import ix
from conductor.clarisse.scripted_class import frames_ui, variables
from conductor.native.lib.gpath_list import PathList
from conductor.native.lib.gpath import Path, GPathError

from conductor.native.lib.sequence import Sequence

RX_HASH = re.compile(r"#+")
RX_FRAME = re.compile(r"\$(\d?)F")
RX_FRAME_FORMAT = re.compile(r"\{frame:\d*d}")
RX_UDIM = re.compile(r"<UDIM>")
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
    # result.add(*_get_references(obj, policy))
    return result


def _get_extra_uploads(obj):
    """Get extra uploads from the extra_uploads attribute."""
    extras_attr = obj.get_attribute("extra_uploads")
    paths = ix.api.CoreStringArray()
    extras_attr.get_values(paths)
    return paths


def _is_project_reference(attr):
    """Does the attribute reference a clarisse project?

    If so, we don't include it in the depedency scan because it will
    ultimately be made local. Check the extension, because Alembic and
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
    """Evaluate the static part of the expression. Assume expression is in active state, otherwise we wouldn't be here. Problem is, we don't want to evaluate frame numbers"""

    orig_expr = target_attr.get_expression()

    # substitute every occurrence of $\d?F with a named python template reflecting
    # the correct value of d, which is the padding.
    # IN: "$CDIR/$2F/foo/$5F/image.$4F.jpg"
    # OUT: "/path/to/project/{frame:02d}/foo/{frame:05d}/image.{frame:04d}.jpg"
    #
    # IN: "$CDIR/$2F/foo/$5F/image.$4F.jpg"
    # OUT: "/path/to/project/{frame:02d}/foo/{frame:05d}/image.{frame:04d}.jpg"

    static_expr = re.sub(r'\$(\d?)F', lambda match: "{{frame:0{:d}d}}".format(
        int(match.group(1) or 0)), orig_expr)

    target_attr.set_expression(static_expr)
    result = target_attr.get_string()
    target_attr.set_expression(orig_expr)
    return result


# print expr.format(frame=17)

# # attr.activate_expression(False)
# # attr.get_serialized_string()

# print attr.get_string()

#     expr = re.sub(r'\$(\d?)F', lambda match: "{{frame:0{:d}d}}".format(
#         int(match.group(1) or 0)), expr)
#             result.append(format_template.format(frame=17))
#         return result


    # get the expression
    # replace $4F with {frame:04d}




# def _resolve_single_filename(attr, policy):

#     # static_vars = variables.get_static()
#     # is_x = attr.is_expression_enabled() and attr.is_expression_activated()
#     # if is_x:
#     #     filename = _evaluate_static_expression(attr)
#     # else:
#     #     filename = attr.get_string()

 
#     # print "_resolve_single_filename attr",attr.get_parent_object().get_name() +"."+ attr.get_name(), ":", filename
#     filename = RX_UDIM.sub("*", filename)
#     print attr.get_name(), ":",  filename
#     if policy == GLOB:
#          filename = re.sub((r"(#+|\$\d?F)"), "*", filename)

#     print "Past Glob Test", filename
    

#     # try:

#     #     print "TRY:", attr.get_name(), ":",  filename
#     #     return Path(filename, context=static_vars).posix_path()

#     # except GPathError as ex:
#     #     print "FAILED", filename, 
#     #     ix.log_warning("{} {}.".format(filename, ex.message()))
#     #     ix.flush(0)
#     #     return filename


def _resolve_file_paths(obj, policy):
    """Scan all path attrs for dependencies according to the given policy.

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
        if _should_ignore(attr):
            continue
        
        if attr.is_expression_enabled() and attr.is_expression_activated():
            # _evaluate_static_expression means to resolve all dollar variables
            # i.e. system, builtin, and so on. It does not evaluate time varying 
            # expression segments such as $4F. Instead it replaces them with python
            # format template. {frame}
            filename = _evaluate_static_expression(attr)
        else:
            filename = attr.get_string()


        if not filename:
            continue
        
        # always glob udims
        filename = RX_UDIM.sub("*", filename)

        if policy == GLOB:
            # replace all frame identifiers with "*" for globbing later
            filename = re.sub((r"(#+|\{frame:\d*d})"), "*", filename)
            result.append(filename)
        else: # SMART
 
            filenames = _smart_expand(obj, attr, filename)
            # print "SMART: "
            # print fns
            result += filenames

    print "_resolve_file_paths" , result
 
    return result

def _smart_expand(obj, attr, filename):

    result = []
    main_seq = frames_ui.main_frame_sequence(obj)

    sequences = None



    resolve_hashes = RX_HASH.search(filename)
    resolve_frame_format = RX_FRAME_FORMAT.search(filename)


    if resolve_hashes:
        # print "resolve_hashes for", filename
        sequences = _attribute_sequence(attr, main_seq)
        if sequences:
            result = sequences["attr_sequence"].expand(filename)
            if resolve_frame_format:
                result = sequences["render_sequence"].expand_format(*result)
    elif resolve_frame_format:
        # print "resolve_frame_format ONLY for", filename
        print "Filename is ", filename
        print main_seq
        result = main_seq.expand_format(filename)
        # print result
    else:
        # print "NO hashes (that intersect) or frame_format_expr for", filename
        result = [filename]
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


def _attribute_sequence(attr, intersector):
    """Get the sequence associated with a filename attribute.

    Many attributes have an associated sequence_mode attribute, which
    when set to 1 signifies varying frames, and makes available start,
    end, and offset attributes to help specify the sequence. Work out the intersection with main sequence ecause during dependency
    scanning, we can optimize the number of frames to upload if we use only those frames specified
    in the sequence attribute, and intersect them with the frame range
    specified in the job node.
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
    offset = obj.get_attribute("frame_offset").get_long()

    seq = Sequence.create(start, end, 1).offset(offset)
    seq = seq.intersection(intersector)
    if not seq:
        # The attribute doesn't intersect the render frames
        return
    # Make a copy of the sequence while at the render frames
    render_seq = Sequence(str(seq))
    attr_seq = seq.offset(-offset)
    return {"attr_sequence":attr_seq, "render_sequence": render_seq}





