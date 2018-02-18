"""Manage the list of takes to be rendered.

Most of the functions in this file are concerned with
building and refreshing the list of takes. We recurse down
the takes hierarchy to get the takes in the correct order
for a tree like display. Parm names are "take_<takename>"
because if they were simply <takename> there could be a name
clash. Each time we refresh, we delete all the old widgets
and rebuild, remembering any ON values. Unfortunately there
are no events emitted when takes are added or deleted, and
there is no way to detect if a tab changed in the param
group, so we have to provide a refresh button.

ptg variable is the parmTemplateGroup.

"""

import hou

FOLDER_PATH = ("Takes", "Render takes")


def _to_parm_name(take_name):
    """Prefix with take_ to avoid parm name clashes."""
    return "take_%s" % take_name


def _takes_with_depth(take, depth, result):
    """Recurse to get a take and its children."""
    result.append((take.name(), depth))
    depth = depth + 1
    for child in take.children():
        _takes_with_depth(child, depth, result)


def get_takes_with_depth():
    """Generate list of takes in order with their depth."""
    result = []
    _takes_with_depth(hou.takes.rootTake(), 0, result)
    return result


def _get_toggle_names(ptg):
    """Get names of existing toggles."""
    folder = ptg.findFolder(FOLDER_PATH)
    return [t.name() for t in folder.parmTemplates()
            if t.type().name() == "Toggle"]


def _remove_toggles(node):
    """Remove existing toggles in preparation to build new."""
    ptg = node.parmTemplateGroup()
    toggles = _get_toggle_names(ptg)
    for toggle in toggles:
        ptg.remove(toggle)
    node.setParmTemplateGroup(ptg)


def _create_toggle_parm(take):
    """Generate a toggle widget for a take tup(takename, depth)."""
    take_name, depth = take
    name = _to_parm_name(take_name)
    indent = ("-    " * depth)
    label = "%s%s" % (indent, take_name)
    tags = {
        "script_callback": "hou.pwd().hdaModule().takes(**kwargs)",
        "script_callback_language": "python"
    }
    return hou.ToggleParmTemplate(name, label, tags=tags)


def _add_toggles(node, takes):
    """Create new toggles representing hierarchy of takes."""
    ptg = node.parmTemplateGroup()
    for take in takes:
        ptg.appendToFolder(FOLDER_PATH, _create_toggle_parm(take))
    node.setParmTemplateGroup(ptg)


def _get_existing_values(node):
    """Remember a map of exiting takes that are enabled."""
    ptg = node.parmTemplateGroup()
    names = _get_toggle_names(ptg)
    result = {}
    for name in names:
        val = node.parm(name).eval()
        if val:
            result[name] = val
    return result


def _set_values(node, values):
    """Set remembered values on new toggles."""
    for key, value in values.iteritems():
        if (node.parm(key)):
            node.parm(key).set(value)


def update_takes(node, **kw):
    """Public function to rebuild the list of controls.

    The list represents the hierarchy of takes.

    """
    takes = get_takes_with_depth()
    values = _get_existing_values(node)
    _remove_toggles(node)
    _add_toggles(node, takes)
    if not values:
        values["take_Main"] = 1
    _set_values(node, values)


def on_toggle_change(node, parm_name, **kw):
    """Do not allow the last ON toggle to be turned off."""
    values = _get_existing_values(node)
    if not values:
        node.parm(parm_name).set(1)
