"""Handle button presses to submit and preview jobs.

Preview, open a window containing the submission script JSON, and
eventually also the structure of the submission and the JSON objects
that will be sent to Conductor.

Submit, send jobs straight to Conductor.
"""
import os
import ix
import conductor.clarisse.utils as cu
from conductor.clarisse.scripted_class import preview_ui
from conductor.clarisse.scripted_class.submission import Submission
from conductor.native.lib.data_block import PROJECT_NOT_SET, ConductorDataBlock
from conductor.native.lib.gpath_list import PathList

SUCCESS_CODES_SUBMIT = [201, 204]

SUBMIT_DIRECT = 0
PREVIEW_FIRST = 1
WRITE_PACKAGE_ONLY = 2

SAVE_STATE_UNMODIFIED = 0
SAVE_STATE_CANCELLED = 1
SAVE_STATE_SAVED = 2
SAVE_STATE_NO = 3
SAVE_STATE_DONT_CARE = 4


def check_need_save(node, which):
    """
    Check if the current project is modified and proposed to save it.

    If user chooses to save, then save it and return the filename along
    with an enum response.


    Args:
        node (ConductorJob):
        which (Enum): Why we are checking.
            SUBMIT_DIRECT, PREVIEW_FIRST, WRITE_PACKAGE_ONLY

    Returns:
        tuple(Enum, Filename):
            SAVE_STATE_UNMODIFIED
            SAVE_STATE_CANCELLED
            SAVE_STATE_SAVED
            SAVE_STATE_NO
            SAVE_STATE_DONT_CARE

    """

    if not node.get_attribute("localize_contexts").get_bool():
        return SAVE_STATE_DONT_CARE, None
    if which == SUBMIT_DIRECT:
        msg = "Save the project?\nYou must save the project if you wish to submit."
    elif which == PREVIEW_FIRST:
        msg = "Save the project?\nClick YES to preview with the option to submit.\nClick NO to preview only."
    else:  # WRITE_PACKAGE_ONLY
        msg = "Save the project?\nYou must save the project if you wish to export a render package."

    response = ix.api.AppDialog.cancel()
    app = ix.application
    if not ix.application.is_project_modified():
        return SAVE_STATE_UNMODIFIED, None
    cwin = ix.application.get_event_window()
    box = ix.api.GuiMessageBox(
        app, 0, 0, "Conductor Information - project not saved!", msg
    )
    x = (2 * cwin.get_x() + cwin.get_width() - box.get_width()) / 2
    y = (2 * cwin.get_y() + cwin.get_height() - box.get_height()) / 2
    box.resize(x, y, box.get_width(), box.get_height())
    if which == SUBMIT_DIRECT or which == WRITE_PACKAGE_ONLY:
        box.set_style(ix.api.AppDialog.STYLE_YES_NO)
    else:
        box.set_style(ix.api.AppDialog.STYLE_YES_NO_CANCEL)

    box.show()
    response = box.get_value()
    box.destroy()

    if response.is_cancelled():
        return SAVE_STATE_CANCELLED, None
    if response.is_no():
        return SAVE_STATE_NO, None

    # response is yes
    current_filename = ix.application.get_current_project_filename()

    if current_filename == "":
        current_filename = "untitled"
    filename = ix.api.GuiWidget.save_file(
        app, current_filename, "Save Scene File...", "Project Files\t*." + "project"
    )
    if filename:
        ix.application.save_project(filename)
        return SAVE_STATE_SAVED, filename
    else:
        return SAVE_STATE_CANCELLED, None


def submit(*args):
    """
    Validate and submit directly.
    """
    node = args[0]

    state, fn = check_need_save(node, SUBMIT_DIRECT)
    if state not in [SAVE_STATE_UNMODIFIED, SAVE_STATE_SAVED, SAVE_STATE_DONT_CARE]:
        ix.log_warning("Submission cancelled.")
        return
    _validate_images(node)
    _validate_packages(node)

    with cu.waiting_cursor():
        submission = Submission(node)
        responses = submission.submit()

    preview_ui.show_submission_responses(responses)


def preview(*args):
    """
    Validate and show the script in a panel.

    Submission can be invoked from the preview panel.
    """
    node = args[0]

    state, _ = check_need_save(node, PREVIEW_FIRST)
    if state == SAVE_STATE_CANCELLED:
        ix.log_warning("Preflight cancelled.")
        return
    can_submit = state in [
        SAVE_STATE_UNMODIFIED,
        SAVE_STATE_SAVED,
        SAVE_STATE_DONT_CARE,
    ]

    _validate(node)
    with cu.waiting_cursor():
        submission = Submission(node)
    preview_ui.build(submission, can_submit=can_submit)


def _validate(node):
    _validate_images(node)
    _validate_packages(node)
    _validate_project(node)


def _validate_images(node):
    """
    Check that images or layers are present and set up to be rendered.

    Also check that the when there are many output paths, their common path is
    not the filesystem root, as this will be the submission's output_path
    property.

    Args:
        node (ConductorJob): Node
    """
    images = ix.api.OfObjectArray()
    node.get_attribute("images").get_values(images)
    out_paths = PathList()
    if not images.get_count():
        ix.log_error("No render images. Please reference one or more image items")

    for image in images:
        if not image.get_attribute("render_to_disk").get_bool():
            ix.log_error(
                "Image does not have render_to_disk attribute set: {}".format(
                    image.get_full_name()
                )
            )

        save_path = image.get_attribute("save_as").get_string()
        if not save_path:
            ix.log_error(
                "Image save_as path is not set: {}".format(image.get_full_name())
            )
        if save_path.endswith("/"):
            ix.log_error(
                "Image save_as path must be a filename, \
                not a directory: {}".format(
                    image.get_full_name()
                )
            )

        try:
            directory = os.path.dirname(save_path)
            out_paths.add(directory)
        except ValueError as ex:
            ix.log_error("{} - while resolving {}".format(str(ex), directory))

    common_path = out_paths.common_path()

    paths = "\n".join(p.posix_path() for p in out_paths)

    if common_path.depth == 0:
        ix.log_error(
            "Your output files should be rendered to a common subfolder.  Not the filesystem root. {}\n{}".format(
                common_path.posix_path(), paths
            )
        )


def _validate_packages(obj):
    """
    Make sure a Clarisse version is selected.

    Args:
        obj (ConductorJob):
    """
    if not (
        obj.get_attribute("clarisse_version")
        .get_applied_preset_label()
        .startswith("clarisse")
    ):
        ix.log_error("No Clarisse package selected.")


def _validate_project(obj):
    """
    Check the project is set.

    Args:
        obj (ConductorJob):
    """
    projects = ConductorDataBlock().projects()
    project_att = obj.get_attribute("conductor_project_name")
    label = project_att.get_applied_preset_label()
    if label == PROJECT_NOT_SET["name"]:
        ix.log_error('Project is not set for "{}".'.format(obj.get_name()))
    try:
        next(p for p in projects if str(p["name"]) == label)
    except StopIteration:
        ix.log_error(
            'Cannot find project "{}" at Conductor. \
                Please ensure the PROJECT dropdown contains a \
                valid project.'.format(
                label
            )
        )
