"""Handle button presses to submit and preview jobs.

Preview, open a window containing the submission script JSON, and
eventually also the structure of the submission and the JSON objects
that will be sent to Conductor.

Submit, send jobs straight to Conductor.
"""

import conductor.clarisse.utils as cu
import ix
from conductor.clarisse.scripted_class import preview_ui
from conductor.clarisse.scripted_class.submission import Submission
from conductor.native.lib.data_block import PROJECT_NOT_SET, ConductorDataBlock

SUCCESS_CODES_SUBMIT = [201, 204]

SUBMIT_DIRECT = 0
PREVIEW_FIRST = 1
WRITE_PACKAGE_ONLY = 2


SAVE_STATE_UNMODIFIED = 0
SAVE_STATE_CANCELLED = 1
SAVE_STATE_SAVED = 2
SAVE_STATE_NO = 3


def check_need_save(which):
    """Check if the current project is modified and proposed to save it.

    If user chooses to save, then save it and return the filename along
    with an enum response.
    """
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

    clarisse_window = ix.application.get_event_window()
    box = ix.api.GuiMessageBox(
        app, 0, 0, "Conductor Information - project not saved!", msg)
    x = (2 * clarisse_window.get_x() +
         clarisse_window.get_width() - box.get_width()) / 2
    y = (2 * clarisse_window.get_y() +
         clarisse_window.get_height() - box.get_height()) / 2
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

    # response.is_yes()
    current_filename = ix.application.get_current_project_filename()

    if current_filename == "":
        current_filename = "untitled"
    filename = ix.api.GuiWidget.save_file(
        app,
        current_filename,
        "Save Scene File...",
        "Project Files\t*." +
        "project")
    if filename != "":
        ix.application.save_project(filename)
        return SAVE_STATE_SAVED, filename

    else:
        return SAVE_STATE_CANCELLED, None


def submit(*args):
    """Validate and submit directly."""
    state, fn = check_need_save(SUBMIT_DIRECT)
    if state not in [SAVE_STATE_UNMODIFIED, SAVE_STATE_SAVED]:
        ix.log_warning("Submission cancelled.")
        return
    obj = args[0]
    _validate_images(obj)
    _validate_packages(obj)

    with cu.waiting_cursor():
        submission = Submission(obj)
        responses = submission.submit()

    preview_ui.show_submission_responses(responses)


def preview(*args):
    """Validate and show the script in a panel.

    Submission can be invoked from the preview panel.
    """
    state, fn = check_need_save(PREVIEW_FIRST)
    if state == SAVE_STATE_CANCELLED:
        ix.log_warning("Preview cancelled.")
        return
    can_submit = state in [SAVE_STATE_UNMODIFIED, SAVE_STATE_SAVED]
    obj = args[0]
    _validate(obj)
    with cu.waiting_cursor():
        submission = Submission(obj)
    preview_ui.build(submission, can_submit=can_submit)


def export_render_package(*args):
    """Just prepare and export the render package.

    Useful if the user wants to run one of the commands on it locally.
    """
    state, fn = check_need_save(PREVIEW_FIRST)
    if state not in [SAVE_STATE_UNMODIFIED, SAVE_STATE_SAVED]:
        ix.log_warning("Export cancelled.")
        return
    obj = args[0]
    _validate_images(obj)
    with cu.waiting_cursor():
        submission = Submission(obj)
        submission.write_render_package()


def _validate(obj):
    _validate_images(obj)
    _validate_packages(obj)
    _validate_project(obj)


def _validate_images(obj):
    """Check some images are present to be rendered.

    Then check that they are set up to save to disk.
    """
    images = ix.api.OfObjectArray()
    obj.get_attribute("images").get_values(images)
    if not images.get_count():
        ix.log_error(
            "No render images. Please reference one or more image items")

    for image in images:
        if not image.get_attribute("render_to_disk").get_bool():
            ix.log_error(
                "Image does not have render_to_disk attribute set: {}".format(
                    image.get_full_name()))

        save_path = image.get_attribute("save_as").get_string()
        if not save_path:
            ix.log_error(
                "Image save_as path is not set: {}".format(
                    image.get_full_name()))
        if save_path.endswith("/"):
            ix.log_error(
                "Image save_as path must be a filename, \
                not a directory: {}".format(
                    image.get_full_name()))


def _validate_packages(obj):
    # for now, just make sure clarisse is present in packages
    attr = obj.get_attribute("packages")
    paths = ix.api.CoreStringArray()
    attr.get_values(paths)
    if any(path.startswith('clarisse') for path in paths):
        return
    ix.log_error(
        "No Clarisse package detected. \
        Please use the package chooser to find one.")


def _validate_project(obj):

    projects = ConductorDataBlock().projects()
    project_att = obj.get_attribute("conductor_project_name")
    label = project_att.get_applied_preset_label()
    if label == PROJECT_NOT_SET["name"]:
        ix.log_error("Project is not set for \"{}\".".format(obj.get_name()))
    try:
        next(p for p in projects if str(p["name"]) == label)
    except StopIteration:
        ix.log_error(
            "Cannot find project \"{}\" at Conductor. Please ensure the PROJECT dropdown contains a valid project.".format(label))
