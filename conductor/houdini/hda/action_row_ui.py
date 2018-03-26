"""Handle button presses to submit and test jobs.

preview: Open a window displaying the structure of the submission and
the JSON objects that will be sent to Conductor.

local: Run the submission tasks on the local machine. This is for debugging
purposes and will be removed.

submit: Send jobs to Conductor
"""
import sys
import traceback
import subprocess
import shlex
import json
import hou

from conductor.lib import conductor_submit
from conductor.houdini.hda.submission import Submission
from conductor.houdini.hda.submission_preview import SubmissionPreview


def _create_submission_with_save(node):
    """Save the scene and return a submission object.

    If user has selected to automatically save a timestamped
    scene, build the submission object first and use the
    scene name it provides. Otherwise use the current scene
    name, and in the case there are unsaved changes, present
    the save-scene flow. In the latter case, build the
    submission object after save so it has the name chosen
    by the user.
    """
    if node.parm("use_timestamped_scene").eval():
        current_scene_name = hou.hipFile.basename()
        submission = Submission(node)
        hou.hipFile.save(file_name=submission.scene)
        hou.hipFile.setName(current_scene_name)
    else:
        if hou.hipFile.hasUnsavedChanges():
            save_file_response = hou.ui.displayMessage(
                """There are unsaved changes and
                timestamped save is turned off!
                Save the file before submitting?""",
                buttons=(
                    "Yes",
                    "No",
                    "Cancel"),
                close_choice=2)
            if save_file_response == 2:
                return
            if save_file_response == 0:
                hou.hipFile.save()
        submission = Submission(node)
    return submission


def preview(node, **_):
    """Display a dry-run submission object in a window.

    There are 2 tabs. One to show the whole object including
    variables available to the user, and one to show the
    JSON for the jobs that will be submitted. NOTE: the
    window is attached to the Houdini session so that it
    persists.
    """
    submission = Submission(node)
    submission_preview = SubmissionPreview()
    submission_preview.tree.populate(submission)
    args_list = submission.get_args()
    jobs = json.dumps(args_list, indent=3, sort_keys=True)
    submission_preview.dry_run.populate(jobs)
    submission_preview.show()
    hou.session.conductor_preview = submission_preview


def local(node, **_):
    """Make a submission and run its tasks locally.

    This is only for testing / debugging and will be
    removed.
    """
    submission = _create_submission_with_save(node)
    if not submission:
        return
    for job in submission.jobs:
        for task in job.tasks:
            args = shlex.split(task.command)
            subprocess.call(args)


def submit(node, **_):
    """Build a submission and submit all its jobs to Conductor.

    We collect and return the responses in a list. If any
    jobs fail the exception is caught so later jobs can
    still be attempted.
    """
    responses = []
    submission = _create_submission_with_save(node)
    for job_args in submission.get_args():
        try:
            remote_job = conductor_submit.Submit(job_args)
            response, response_code = remote_job.main()
            responses.append({"code": response_code, "response": response})
        except BaseException:
            responses.append(
                {"error": "".join(traceback.format_exception(*sys.exc_info()))})
    return responses
