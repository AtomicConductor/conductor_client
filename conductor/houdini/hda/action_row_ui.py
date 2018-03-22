"""Entry point for job submission."""
import sys
import traceback
import subprocess
import shlex
import json
import hou

from conductor.lib import conductor_submit
from conductor.houdini.hda.submission import Submission
from conductor.houdini.hda.submission_preview import SubmissionPreview
# from conductor.houdini.hda.submission_dry_run import SubmissionDryRun
# from conductor.houdini.hda.submission_dry import SubmissionDry


def preview(node, **_):
    submission = Submission(node)
    submission_preview = SubmissionPreview()
    submission_preview.tree.populate(submission)

    args_list = submission.remote_args()
    j = json.dumps(args_list, indent=3, sort_keys=True)

    submission_preview.dry_run.populate(j)

    submission_preview.show()
    hou.session.conductor_preview = submission_preview


# def dry_run(node, **_):
   
#     args_list = submission.remote_args()
#     j = json.dumps(args_list, indent=3, sort_keys=True)
#     submission_dry = SubmissionDry()
#     submission_dry.populate(j)
#     submission_dry.show()
#     hou.session.conductor_dry = submission_dry



def _create_submission_with_save(node):
    if node.parm("use_timestamped_scene").eval():
        current_scene_name = hou.hipFile.basename()
        # generates the timestamp etc.
        submission = Submission(node)
        hou.hipFile.save(file_name=submission.scene)
        hou.hipFile.setName(current_scene_name)

    # use existing scene name
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

        # make the submission after manual save in case the user changed the
        # name during save
        submission = Submission(node)

    return submission

 

def local(node, **_):

    submission = _create_submission_with_save(node)
    if not submission:
        return
    for job in submission.jobs:
        for task in job.tasks:
            args = shlex.split(task.command)
            subprocess.call(args)


def doit(node, **_):
    responses = []
    submission = _create_submission_with_save(node)
    for job_args in submission.remote_args():
        try:
            remote_job = conductor_submit.Submit(job_args)
            response, response_code = remote_job.main()
            responses.append({"code":response_code, "response":  response})
        except BaseException:
            responses.append({"error": "".join(traceback.format_exception(*sys.exc_info()))})
    return responses
