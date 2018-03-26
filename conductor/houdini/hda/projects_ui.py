"""Manage project menu selection."""

from conductor.houdini.hda import uistate
from conductor.houdini.lib import data_block


def populate_menu(node):
    """Populate project menu.

    Get list of items from the shared data_block where they
    have been cached. The menu needs a flat array: [k, v, k,
    v ....]
    """
    projects = data_block.ConductorDataBlock(product="houdini").projects()
    selected = node.parm('project').eval()
    if selected not in (project["id"] for project in projects):
        node.parm('project').set(projects[0]["id"])
    res = [k for i in projects for k in (i["id"], i["name"])]
    return res


def select(node, **_):
    """When user chooses a new project, update button states."""
    uistate.update_button_state(node)
