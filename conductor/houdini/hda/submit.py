"""Entry point for job submission."""
import sys
import traceback
import subprocess
import shlex
import hou

from conductor.lib import conductor_submit
from conductor.houdini.hda.submission import Submission
from conductor.houdini.hda.submission_tree import SubmissionTree


def dry_run(node, **_):
    submission = Submission(node)
    submission_tree = SubmissionTree()
    submission_tree.populate(submission)
    submission_tree.show()
    hou.session.dummy = submission_tree


def create_submission_with_save(node):
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
                "Unsaved changes! Save the file before submitting?",
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

    submission = create_submission_with_save(node)
    print "submission.scene: %s" % submission.scene
    print "submission.use_timestamped_scene: %s" % submission.use_timestamped_scene

    for job in submission.jobs:
        print "Running job %s" % job.title
        for task in job.tasks:
            print "Running task %s" % task.command
            args = shlex.split(task.command)
            subprocess.call(args)


def doit(node, **_):
    submission = create_submission_with_save(node)

    submission_args = submission.remote_args()

    for job in submission.jobs:
        print "Submitting job %s" % job.title

        job_args = job.remote_args(submission_args)

        try:
            remote_job = conductor_submit.Submit(job_args)
            response, response_code = remote_job.main()
        except BaseException:
            message = "".join(traceback.format_exception(*sys.exc_info()))
            hou.ui.displayMessage(title="Job submission failure", text=message,
                                  severity=hou.severityType.Error)
            raise
        return response_code, response
