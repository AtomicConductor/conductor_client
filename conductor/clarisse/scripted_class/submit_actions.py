"""Handle button presses to submit and preview jobs.

preview: Open a window, eventually, displaying the structure of
the submission and the JSON objects that will be sent to Conductor.

submit: Send jobs to Conductor
"""
import json
import os
import sys
import traceback
import ix
from conductor import CONFIG
from conductor.clarisse.scripted_class.submission import Submission
from conductor.clarisse.scripted_class import preview_ui
from conductor.lib import conductor_submit

SUCCESS_CODES_SUBMIT = [201, 204]


def submit(obj, _):
    _validate_images(obj)
    _validate_packages(obj)
    submission = Submission(obj)
    submission.submit()


def preview(obj, _):
    _validate_images(obj)
    _validate_packages(obj)
    submission = Submission(obj)
    ui = preview_ui.build(submission)

def _validate_images(obj):
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
    # for now, just make sure clarisse is present
    attr = obj.get_attribute("packages")
    paths = ix.api.CoreStringArray()
    attr.get_values(paths)
    if any(path.startswith('clarisse') for path in paths):
        return
    ix.log_error(
        "No Clarisse package detected. Please use the package chooser to find one.")
