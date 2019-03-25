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
from conductor.lib import conductor_submit

SUCCESS_CODES_SUBMIT = [201, 204]


def submit(obj, _):
    _validate_images(obj)
    submission = Submission(obj)
    _submit(submission)


def preview(obj, _):
    _validate_images(obj)
    submission = Submission(obj)
    submission_args = submission.get_args()

    # show the submission in a window.
    # allow user to press Go to submit
    json_jobs = json.dumps(submission_args, indent=3, sort_keys=True)
    ix.log_info(json_jobs)


def _submit(submission):
    submission_args = submission.get_args()
    submission.write_render_package()
    results = []
    for job_args in submission_args:
        try:
            remote_job = conductor_submit.Submit(job_args)
            response, response_code = remote_job.main()
            results.append({"code": response_code, "response": response})
        except BaseException:
            results.append({"code": "undefined", "response": "".join(
                traceback.format_exception(*sys.exc_info()))})
    for result in results:
        ix.log_info(result)


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
