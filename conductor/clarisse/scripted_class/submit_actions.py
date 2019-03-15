"""Handle button presses to submit and preview jobs.

preview: Open a window displaying the structure of the submission and
the JSON objects that will be sent to Conductor.

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


def _make_all_context_local():
    all_ctx = ix.api.OfContextSet()
    ix.application.get_factory().get_root().resolve_all_contexts(all_ctx)
    ref_ctxs = []

    for i in range(all_ctx.get_count()):
        ctx = all_ctx[i]
        if ctx.is_reference():
            ref_ctxs.append(ctx)

    if len(ref_ctxs) > 0:
        for ctx in ref_ctxs:
            ix.cmds.MakeLocalContext(ctx)


def submit(obj, _):
    _validate_images(obj)
    pass


def preview(obj, _):
    _validate_images(obj)
    submission = Submission(obj)
    args_list = submission.get_args()
    json_jobs = json.dumps(args_list, indent=3, sort_keys=True)
    print json_jobs


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
