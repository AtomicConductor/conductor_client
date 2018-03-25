"""Manage project menu selection."""

from conductor.houdini.hda import uistate
from conductor.houdini.lib import data_block


def populate_menu(node):
    """Populate project menu.

    Get list from the projects param where they are cached.
    If there are none, which can only happen on create, then
    fetch them from the server. If a previous fetch failed,
    there will at least be a NotSet menu item. If we didn't
    implement a NotSet menu item, then there would be
    repeated attempts to hit the server to login which would
    get very annoying.

    """
    projects = data_block.ConductorDataBlock(product="houdini").projects()
    selected = node.parm('project').eval()
    if selected not in (project["id"] for project in projects):
        node.parm('project').set(projects[0]["id"])
    res = [k for i in projects for k in (i["id"], i["name"])]
    return res


def select(node, **_):
    """When user chooses a new project, update the submit button."""
    uistate.update_button_state(node)
