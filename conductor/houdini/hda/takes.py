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
group, so we have to provide a refresh button. ptg variable
is the parmTemplateGroup.

"""
from contextlib import contextmanager
import hou

FOLDER_PATH = ("Takes", "Render takes")

@contextmanager
def take_context(take):
    """Put houdini in the context of a take to run some code.

    I'm not sure if setting the same take causes a
    dependency update so so just in case, the take changing
    code only happens if we are not already on the desired
    take

    """
    current = hou.takes.currentTake()
    if current != take:
        hou.takes.setCurrentTake(take)
    yield
    if current != take:
        hou.takes.setCurrentTake(current)

def _to_parm_name(take_name):
    """Prefix take name with take_ to avoid parm name clashes."""
    return "take_%s" % take_name

def enable_for_current(node, *parm_tuple_names):
    """Enable parm dependencies for the current take.

    Some parms are automatically updated when other parms
    change. If the controlled parms are not included in the
    take then houdini throws an error. So any function that
    updates other parms should pass those parms' parm_tuple
    names to this function first.

    """
    parm_tuples = [node.parmTuple(name) for name in parm_tuple_names]
    take = hou.takes.currentTake()
    if not take == hou.takes.rootTake():
        for parm_tuple in parm_tuples:
            if not take.hasParmTuple(parm_tuple):
                take.addParmTuple(parm_tuple)


def _takes_with_depth(take, depth, result):
    """Recurse to get a take and its children."""
    result.append((take.name(), depth))
    for child in take.children():
        _takes_with_depth(child, depth + 1, result)


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
    """Generate a toggle widget for a take tup(takename, depth).

    Note, the takes tag is false, because of course you
    can't have a different set of takes active for each
    take.

    """
    take_name, depth = take
    name = _to_parm_name(take_name)
    indent = ("-    " * depth)
    label = "%s%s" % (indent, take_name)
    tags = {
        "script_callback": "hou.pwd().hdaModule().takes(**kwargs)",
        "script_callback_language": "python",
        "takes": "False"
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
        if node.parm(key):
            node.parm(key).set(value)


def update_takes(node, **_):
    """Rebuild the list of controls.

    The list represents the hierarchy of takes.

    """
    takes = get_takes_with_depth()
    values = _get_existing_values(node)
    _remove_toggles(node)
    _add_toggles(node, takes)
    if not values:
        root_param = _to_parm_name(hou.takes.rootTake().name())
        values[root_param] = 1
    _set_values(node, values)
    # _sync_parms_to_active_takes(node)


def on_toggle_change(node, parm_name, **_):
    """Do not allow the last ON toggle to be turned off."""
    values = _get_existing_values(node)
    if not values:
        node.parm(parm_name).set(1)
    # _sync_parms_to_active_takes(node)


def active_takes(node):
    """Active takes are the list of takes we want to submit"""
    active = _get_existing_values(node)
    result = []
    for take in hou.takes.takes():
        if active.get(_to_parm_name(take.name())):
            result.append(take)
    return result
