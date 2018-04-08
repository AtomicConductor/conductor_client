"""Handle button presses to submit and test jobs.

preview: Open a window displaying the structure of the submission and
the JSON objects that will be sent to Conductor.

submit: Send jobs to Conductor
"""
import os
import sys
import traceback
import json
import hou

from conductor import CONFIG
from conductor.lib import conductor_submit
from conductor.houdini.hda.submission import Submission
from conductor.houdini.hda.submission_preview import SubmissionPreview

SUCCESS_CODES_SUBMIT = [201, 204]


def _save_scene_or_use_current():
    """Save scene flow"""
    fn = hou.hipFile.path()
    save_file_response = hou.ui.displayMessage(
        title='Unsaved changes',
        text="What would you like to do?",
        buttons=(
            "Save and submit",
            "Submit existing scene",
            "Cancel"),
        close_choice=2)
    if save_file_response == 2:
        return None
    if save_file_response == 0:
        fn = hou.ui.selectFile(
            start_directory=os.path.dirname(hou.hipFile.path()),
            title="Save",
            file_type=hou.fileType.Hip,
            pattern="*.hip,*.hiplc,*.hipnc,*.hip*",
            default_value=hou.hipFile.basename(),
            chooser_mode=hou.fileChooserMode.Write)
        if fn:
            hou.hipFile.save(file_name=fn)
    if save_file_response == 1:
        # When use current, just  make sure the file exists.
        # Will throw otherwise
        hou.findFile(fn)

    return fn


def _create_submission_with_save(node):
    """Save the scene and return a submission object.

    If user has selected to automatically save a timestamped
    scene, build the submission object first and use the
    timestamped scene name it provides.

    Otherwise in the case there are unsaved
    changes, present the save-scene flow.
    """

    if node.parm("use_timestamped_scene").eval():
        current_scene_name = hou.hipFile.basename()
        submission = Submission(node)
        hou.hipFile.save(file_name=submission.scene)
        hou.hipFile.setName(current_scene_name)
    else:
        if hou.hipFile.hasUnsavedChanges():
            if not _save_scene_or_use_current():
                return None
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


def _display_submission_results(results):

    msgType = hou.severityType.Message
    summaries = []
    details = []
    for result in results:
        code = result["code"]
        response = result.get("response")
        if code in SUCCESS_CODES_SUBMIT:
            jobid = "job/%05d" % int(response.get("jobid") or 0)
            url = "%s/%s" % (CONFIG['url'], jobid)

            summaries.append("Job submitted: %s" % jobid)
            details.append("Submitted to: %s" % url)

        else:
            msgType = hou.severityType.ImportantMessage
            if code == "undefined":
                summaries.append("Job failed")
                details.append(response)
            elif code == "cancelled":
                summaries.append("Submission cancelled")
            else:
                summaries.append("Job failed with code: %s" % code)

    summary = "\n".join(summaries)
    detail = "\n".join(details)

    hou.ui.displayMessage(title='Submission response', text=summary,
                          details_label="Show details",
                          details=detail,
                          severity=msgType)


def submit(node, **_):
    """Build a submission and submit all its jobs to Conductor.

    We collect the responses in a list. If any jobs fail the
    exception is caught so subsequent jobs can still be
    attempted.
    """
    results = []
    submission = _create_submission_with_save(node)

    if submission:
        for job_args in submission.get_args():
            try:
                remote_job = conductor_submit.Submit(job_args)
                response, response_code = remote_job.main()
                results.append({"code": response_code, "response": response})
            except BaseException:
                results.append({"code": "undefined", "response": "".join(
                    traceback.format_exception(*sys.exc_info()))})
    if results:
        _display_submission_results(results)
