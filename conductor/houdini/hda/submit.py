"""Entry point for job submission."""

from conductor.houdini.hda import submission

def show_request(node, **_):
    """TODO in CT-59 generate request and open a panel.

    Should be instant and not mutate anything. Therefore, do
    not save a file or actually submit anything.

    """
    sub =  submission.Submission(node)
    sub.dry_run()

 

def doit(node, **_):
    # print "CREATE SUBMISSION"
    # submission = Submission(node, takes.active_takes(node))
    # submission.view()
    """TODO  in CT-59 submit jobs."""

    # if hou.hipFile.hasUnsavedChanges():
    #     save_file_response = hou.ui.displayMessage(
    #         "There are some unsaved changes. Do you want to save the file before "
    #         "submitting to Conductor?", buttons=(
    #             "Yes", "No", "Cancel"), close_choice=2)
    #     if save_file_response == 2:
    #         return
    #     if save_file_response == 0:
    #         hou.hipFile.save()
    # hou.ui.displayMessage(text='Job submitted')

