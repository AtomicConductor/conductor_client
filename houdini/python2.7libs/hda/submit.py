"""Entry point for job submission."""
import render_source
import projects


def _can_submit(node):
    """TODO in CT-59 determine if everything is valid for a submission to
    happen.

    Use this to enable/disable the submit button

    """
    if not render_source.get_render_node(node):
        return False
    if not projects.has_valid_project(node):
        return False
    return True


def show_request(node, **kw):
    """TODO in CT-59 generate request and open a panel.

    Should be instant and not mutate anything. Therefore, do
    not save a file or actually submit anything.

    """
    pass


def doit(node, **kw):
    """TODO  in CT-59 submit jobs."""
    pass
    #     if hou.hipFile.hasUnsavedChanges():
    #         save_file_response = hou.ui.displayMessage(
    #             "There are some unsaved changes. Do you want to save the file before "
    #             "submitting to Conductor?", buttons=(
    #                 "Yes", "No", "Cancel"), close_choice=2)
    #         if save_file_response == 2:
    #             return
    #         if save_file_response == 0:
    #             hou.hipFile.save()
    #     hou.ui.displayMessage(text='Job submitted')


def update_button_state(node):
    """Enable/disable submit button."""
    can_submit = 1 if _can_submit(node) else 0
    node.parm("can_submit").set(can_submit)
