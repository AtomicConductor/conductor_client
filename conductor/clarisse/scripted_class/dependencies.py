"""
Collect dependencies
"""

import os
import re

import ix
from conductor.clarisse.scripted_class import frames_ui
from conductor.native.lib.gpath import Path
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
SEQUENCE_OFFSET_KLUDGE = 100000

# ct_node: wrapper around cnode. Allows us to add flags and so on.

# ct_prep.py: pre render script that operates in the Clarisse. Among other
# things, it emoves drive letters on win.
CONDUCTOR_SCRIPTS = ["ct_prep.py", "ct_cnode"]

# clarisse.cfg: A copy of the users config file.
CLARISSE_CFG_FILENAME = "clarisse.cfg"


def system_dependencies():
    """
    Provides a list of system files to be sent to the render node.

    These will be copied to a directory in preparation for uploading.

    This is part of a strategy to satisfy 2 constraints.
    1. Dont store special logic on the sidecar.
    2. Don't make the render command un-runnable on the local machine.

    See docs in ct_cnode and ct_prep for more info.

    Returns:
        list: Each element is a source/destination pair of paths.
        [
            {"src": "/some/path.ext", "dest": "/other/path.ext"},
            ...
        ]
    """

    result = []
    conductor_scripts_directory = os.path.join(
        os.environ["CONDUCTOR_LOCATION"], "conductor", "clarisse", "scripts"
    )
    conductor_tmp_dir = os.path.join(
        ix.application.get_factory().get_vars().get("CTEMP").get_string(), "conductor"
    )

    for script in CONDUCTOR_SCRIPTS:
        src_path = Path(os.path.join(conductor_scripts_directory, script)).posix_path()
        dest_path = Path(os.path.join(conductor_tmp_dir, script)).posix_path()

        result.append({"src": src_path, "dest": dest_path})

    config_dir = (
        ix.application.get_factory()
        .get_vars()
        .get("CLARISSE_USER_CONFIG_DIR")
        .get_string()
    )

    config_src_file = Path(os.path.join(config_dir, CLARISSE_CFG_FILENAME)).posix_path()
    config_dest_file = Path(
        os.path.join(conductor_tmp_dir, CLARISSE_CFG_FILENAME)
    ).posix_path()

    result.append({"src": config_src_file, "dest": config_dest_file})

    return result


def _get_system_dependencies():
    """
    Extracts the destination side of system dependency files.

    Returns:
        PathList: list of system files to be uploaded
    """
    result = PathList()
    for entry in system_dependencies():
        try:
            result.add(entry["dest"])
        except ValueError as ex:
            ix.log_error(
                "{} - while resolving system_dependency: {}".format(
                    str(ex), entry["dest"]
                )
            )

    return result


def collect(obj):
    """
    Collect ALL upload files in preparation for submission.

    Args:
        obj (ConductorJob): The item whose attributes define the scan.
    Returns:
        PathList: All file dependencies.
    """
    result = PathList()

    # policy: NONE, GLOB, SMART_SEQUENCE
    policy = obj.get_attribute("dependency_scan_policy").get_long()

    # If we are not localizing reference contexts, then we need to add the
    # referenced project files to the dependencies list.
    include_references = not obj.get_attribute("localize_contexts").get_bool()

    result.add(*_get_system_dependencies())
    result.add(*_get_extra_uploads(obj))

    result.add(*get_scan(obj, policy, include_references))

    # tell the list to look on disk and expand  any "*" or <UDIM> in place
    result.glob()

    return result


def _get_extra_uploads(obj):
    """
    Collects any files specified through the extra uploads window.

    They are stored in a list attribute on the ConductorJob item.

    Args:
        obj (ConductorJob): item being processed.

    Returns:
        PathList: Collected paths.
    """
    result = PathList()
    extras_attr = obj.get_attribute("extra_uploads")
    paths = ix.api.CoreStringArray()
    extras_attr.get_values(paths)
    for path in paths:
        try:
            result.add(path)
        except ValueError as ex:
            ix.log_error(
                "{} - while resolving extra upload path: {}".format(str(ex), path)
            )

    return result


def get_scan(obj, policy, include_references=True):
    """
    Scan all path attrs for dependencies according to the given policy.

    If policy is not None: First replace all UDIM tags with a "*" so they may be
    globbed.

    File sequences may be resolved one of 2 ways:
    1. If policy is GLOB, then hashes in filenames will be replaced by a "*" and
        globbed later.
    2. If policy is SMART then for each filename, we look at its sequence
        definition and calculate the frames that will be needed for the frame
        range being rendered.

    Args:
        obj (ConductorJob): Item being processed.
        policy (Enum): NONE, GLOB, SMART
        include_references (bool, optional): Whether to scan for references. Defaults to True.

    Returns:
        PathList: Collected paths
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
            try:
                result.add(re.sub((r"(#+|\{frame:\d*d})"), "*", filename))
            except ValueError as ex:
                ix.log_error(
                    "{} - while resolving path: {} = {}".format(
                        str(ex), str(attr), filename
                    )
                )

        else:  # SMART
            filenames = _smart_expand(obj, attr, filename)
            try:
                result.add(*filenames)
            except ValueError as ex:
                ix.log_error(
                    "{} - while resolving path: {} = {}".format(
                        str(ex), str(attr), filename
                    )
                )

    # We ignored references in _should_ignore for 2 reasons.
    # 1. We only want them if we are not localizing them
    #    (include_references==True).
    # 2. Getting ref contexts from OfAttr.get_path_attrs() is buggy so it's best
    #    to get them through the root context with resolve_all_contexts()

    # On Windows, we make a new extension for all project reference paths (".ct.project")
    # because we will be replacing them with a linuxified version of the file.
    if include_references:
        refs = _scan_for_references()
        if os.name == "nt":
            for ref in refs:
                if ref.endswith(".project"):
                    result.add(
                        re.sub(
                            r"(\.ct\.project|\.project)",
                            ".ct.project",
                            ref.posix_path(),
                        )
                    )
                else:
                    result.add(ref)
        else:
            result.add(*refs)

    return result


def _scan_for_references():
    result = PathList()
    contexts = ix.api.OfContextSet()
    ix.application.get_factory().get_root().resolve_all_contexts(contexts)
    for context in contexts:
        if context.is_reference() and not context.is_disabled():
            try:
                filename = context.get_attribute("filename").get_string()
                result.add(filename)
            except ValueError as ex:
                ix.log_error(
                    "{} - while resolving reference {}.filename = {}".format(
                        str(ex), str(context), filename
                    )
                )

    return result


def _is_project_reference(attr):
    """
    Does the attribute reference a clarisse project?

    If so, we don't include it in the depedency scan because ultimately it will
    be made local. Check the extension, because Alembic and pixar formats are
    also possible.

    Args:
        attr (OfAttr): Attribute to query

    Returns:
         bool: Is the attribute a reference
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
    """
    Is the attribute needed

    Args:
        attr (OfAttr): Attribute to query

    Returns:
        bool: True if the path at this attribute should be ignored
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
    """
    Evaluate the static part of an attribute containing an expression.

    Assume expression is in active state, (otherwise we wouldn't be here).

    We are doing this because we want literal paths that are needed for the
    upload. The easiest and most reliable way to evaluate variables in the
    expression would be to use get_string(). However, if we do that, it will
    evaluate time varying variables like $3F for the current frame only.

    So to keep the time varying varables variable, we replace them with python named format strings
    like {frame:0nd} where n is the padding.

    NOTE: It does not resolve hash placeholders like ### so we can leave them as is.
    NOTE 2: Can't remember why I used {frame:04d} rather than change to ####.

    $CDIR/bugs_seq/bugs.####.jpg becomes
    /Users/julian/projects/fish/clarisse/bugs_seq/bugs.####.jpg

    $CDIR/bugs_seq/bugs.$4F.jpg becomes
    /Users/julian/projects/fish/clarisse/bugs_seq/bugs.{frame:04d}.jpg

    With these time varying placeholders left intact, we can expand correctly
    later using either the SMART scan policy, or a simple GLOB.

    Args:
        target_attr (OfAttr): Attribute to query,

    Returns:
        string: The attribute value with all $variables resolved except those
        that rely on time.
    """
    orig_expr = target_attr.get_expression()

    static_expr = re.sub(
        r"\$(\d?)F",
        lambda match: "{{frame:0{:d}d}}".format(int(match.group(1) or 0)),
        orig_expr,
    )

    target_attr.set_expression(static_expr)
    result = target_attr.get_string()
    target_attr.set_expression(orig_expr)
    return result


def _smart_expand(obj, attr, filename):
    """
    Expand filenames when policy is SMART.

    Takes into account the frame range to be rendered, and the frame
    specification of any source animated maps along with their offset. Then
    resolves filenames for that intersection of sequences.

    Args:
        obj (ConductorJob):  Item being processed. attr (OfAttr): Attribute to
        query.
        filename (string): File template to expand. It may have hashes
        and/or frame_format {frame:02d} style placeholders to represent frame
        ranges

    Returns:
        list(strings): Expanded filenames
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
    """
    Get the sequence associated with a filename attribute.

    Many attributes have an associated sequence_mode attribute, which when set
    to 1 signifies varying frames and makes available start, end, and offset
    attributes to help specify the sequence.

    We work out the intersection of that sequence with the main sequence because
    during dependency scanning, we can optimize the number of frames to upload
    if we use only those frames specified in the sequence attribute, and
    intersect them with the frame range specified in the job node.

    Args:
        attr (OfAttr): Attribute to query,
        intersector (Sequence): The main sequence as defined by the ConductorJob
        frames override, or by the images being rendered.

    Returns:
        dict:
            The sequence defined by the attribute intersected with the main sequence.
            The sequence the sequence while at the render frames.
    """

    obj = attr.get_parent_object()
    mode_attr = obj.attribute_exists("sequence_mode")
    if not (mode_attr and mode_attr.get_long()):
        ix.log_error("Attribute is not in sequence mode {}")

    global_frame_rate = ix.application.get_prefs(
        ix.api.AppPreferences.MODE_APPLICATION
    ).get_long_value("animation", "frames_per_second")
    attr_frame_rate = obj.get_attribute("frame_rate").get_long()
    if not attr_frame_rate == global_frame_rate:
        ix.log_error(
            "Can't get attribute sequence when global \
            fps is different from fps on the attribute"
        )

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

    seq = Sequence.create(start, end, 1).offset(offset + SEQUENCE_OFFSET_KLUDGE)
    seq = seq.intersection(intersector.offset(SEQUENCE_OFFSET_KLUDGE))

    if not seq:
        # The attribute doesn't intersect the render frames
        return
    # Make a copy of the sequence while at the render frames
    render_seq = Sequence.create(str(seq)).offset(-SEQUENCE_OFFSET_KLUDGE)

    attr_seq = seq.offset(-(offset + SEQUENCE_OFFSET_KLUDGE))

    return {"attr_sequence": attr_seq, "render_sequence": render_seq}
