"""Update buttons based on submission validity.

Currently, a job is valid if it has a project selected, and
if the custom frame range is valid. A Submission is valid if
it has a project selected and all its input jobs are valid.
"""

import json
from conductor.houdini.hda import takes, types
from conductor.houdini.lib import data_block


def has_valid_project(node):
    """Is the project is valid.

    This will be false if the project is set to Not Set, or
    if for some reason it is set to a project name that is
    no longer in the list from Conductor, which could occur
    if a project has been deleted.
    """
    projects = data_block.ConductorDataBlock(product="houdini").projects()
    selected = node.parm('project').eval()
    return not (selected == "notset" or selected not in (
        project["id"] for project in projects))


def _submission_node_can_submit(node):
    """Determine if the submission node can be submitted.

    It must have a valid project. All its job inputs must be
    valid and it must have at least one.
    """
    if not has_valid_project(node):
        return False
    if not node.inputs():
        return False
    for job in node.inputs():
        if job:
            if job.parm("use_custom").eval() and not job.parm(
                    "custom_valid").eval():
                return False
    return True


def _job_node_can_submit(node):
    """Determine if the job node can be submitted.

    It must have a valid project and frame range. Note, the
    frame range can only be invalid if it is set to custom.
    """

    if not node.inputs():
        return False
    if not has_valid_project(node):
        return False

    if node.parm("use_custom").eval() and not node.parm("custom_valid").eval():
        return False
    return True


def update_button_state(node):
    """Update a job or submitter node's buttons."""
    takes.enable_for_current(
        node,
        "can_submit",
        "submit",
        "preview",
        "update",
        "source",
        "driver_type",
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
