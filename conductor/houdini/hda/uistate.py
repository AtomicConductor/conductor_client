import json
from conductor.houdini.hda import takes, types


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
    if not has_valid_project(node):
        return False
    if not node.inputs():
        return False
    for job in node.inputs():
        if job:
            if  job.parm("use_custom").eval() and not  job.parm("custom_valid").eval():
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
 
    if  node.parm("use_custom").eval() and not  node.parm("custom_valid").eval():
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

    if types.is_job_node(node):
        can_submit = int(_job_node_can_submit(node))
        node.parm("can_submit").set(can_submit)

        for output in node.outputs():
            if output and types.is_submitter_node(output):
                update_button_state(output)
    else:
        can_submit = int(_submission_node_can_submit(node))
        node.parm("can_submit").set(can_submit)
