import json
from conductor.houdini.hda import takes 




def has_valid_project(node):
    """Make sure the project is valid.

    This helps determine if the submit button should be
    enabled.

    """
    projects = json.loads(node.parm('projects').eval())
    selected = node.parm('project').eval()
    return not (selected == "notset" or selected not in (
        project["id"] for project in projects))



def _submission_node_can_submit(node):
    """TODO in CT-59 determine if everything is valid for a submission to
    happen.

    Use this to enable/disable the submit button

    """


    if not node.inputs():
        return False
    return True



def _job_node_can_submit(node):
    """TODO in CT-59 determine if everything is valid for a submission to
    happen.

    Use this to enable/disable the submit button

    """


    if not node.inputs():
        return False
    if not has_valid_project(node):
        return False
    return True



def update_button_state(node):
    """Enable/disable submit button."""
    takes.enable_for_current(
        node,
        "can_submit",
        "submit",
        "dry_run",
        "preview",
        "local_test",
        "update",
        "render_source",
        "render_type",
        "jobs")

    _, nodetype, _ = node.type().name().split("::")
    if nodetype == "job":
        can_submit =int(_job_node_can_submit(node))
    else:
        can_submit =int(_submission_node_can_submit(node))
    node.parm("can_submit").set(can_submit)
