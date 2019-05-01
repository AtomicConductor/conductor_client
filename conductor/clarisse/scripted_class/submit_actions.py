"""Handle button presses to submit and preview jobs.

Preview, open a window containing the submission script JSON, and
eventually also the structure of the submission and the JSON objects
that will be sent to Conductor.

Submit, send jobs straight to Conductor.
"""

import ix
from conductor.clarisse.scripted_class.submission import Submission
from conductor.clarisse.scripted_class import preview_ui


SUCCESS_CODES_SUBMIT = [201, 204]

SUBMIT_DIRECT = 0
PREVIEW_FIRST = 1

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
    else:
        msg = "Save the project?\nClick YES to preview with the option to submit.\nClick NO to preview only."

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
    if which == SUBMIT_DIRECT:
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
    # state, fn = check_need_save(SUBMIT_DIRECT)
    # if state not in [SAVE_STATE_UNMODIFIED, SAVE_STATE_SAVED]:
    #     ix.log_warning("Submission cancelled.")
    #     return

    obj = args[0]
    _validate_images(obj)
    _validate_packages(obj)
    submission = Submission(obj)
    submission.submit()


def preview(*args):
    """Validate and show the script in a panel.

    Submission can be invoked from the preview panel.
    """
    # state, fn = check_need_save(PREVIEW_FIRST)
    # if state == SAVE_STATE_CANCELLED:
    #     ix.log_warning("Submission cancelled.")
    #     return
    # can_submit = state in [SAVE_STATE_UNMODIFIED, SAVE_STATE_SAVED]
    obj = args[0]
    _validate_images(obj)
    _validate_packages(obj)
    submission = Submission(obj)
    preview_ui.build(submission)


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
