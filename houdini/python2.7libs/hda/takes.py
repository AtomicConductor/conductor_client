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

import hou

FOLDER_PATH = ("Takes", "Render takes")


def _to_parm_name(take_name):
    """Prefix take name with take_ to avoid parm name clashes."""
    return "take_%s" % take_name


def _is_takable(template):
    """Determine if template is takable.

    It is takable if it has a tag `takes` set to the string
    True, or if it is a label. We enable all labels because
    labels don't have tags so we can't differentiate.

    """
    return (template.type().name() == "Label") or (
        template.tags().get("takes") == "True")


def _takable_templates(parent):
    """Collect templates that have been whitelisted for take inclusion."""
    for template in parent.parmTemplates():
        if _is_takable(template):
            yield template
        if (template.type() == hou.parmTemplateType.Folder and
                template.isActualFolder()):
            for child in _takable_templates(template):
                if _is_takable(child):
                    yield child


def _enable_takable_parms(take, node):
    """Enable all whitelisted parms for this take."""
    ptg = node.parmTemplateGroup()
    for template in _takable_templates(ptg):
        parm_tuple = node.parmTuple(template.name())
        print "%s : %s : %s" % (
            take.name(), template.name(), parm_tuple.name())
        take.addParmTuple(parm_tuple)


def _disable_takable_parms(take, node):
    """Disable all whitelisted parms for this take."""
    ptg = node.parmTemplateGroup()
    for template in _takable_templates(ptg):
        parm_tuple = node.parmTuple(template.name())
        take.removeParmTuple(parm_tuple)


def _sync_parms_to_active_takes(node):
    """Parameters should be enabled for active takes.

    We enable a subset of parameters on the node for takes
    that will be rendered, and disable all parameters for
    all non rendering takes, except the root take, whose
    parameters are always enabled. In order to set parameter
    states for a take, the take must be current. Therefore
    we remember the current take before this procedure and
    set it back afterwards, unless it has somehow been
    turned off (which shouldn't be possible), in which case
    we set the root take to be current.

    """
    remember_current = hou.takes.currentTake()

    for take in hou.takes.takes():
        if take.name() == hou.takes.rootTake().name():
            continue
        hou.takes.setCurrentTake(take)
        parm_name = _to_parm_name(take.name())
        if node.parm(parm_name).eval():
            _enable_takable_parms(take, node)
        else:
            _disable_takable_parms(take, node)
    current_take_parm_name = _to_parm_name(remember_current.name())
    if node.parm(current_take_parm_name).eval():
        hou.takes.setCurrentTake(remember_current)
    else:
        hou.takes.setCurrentTake(hou.takes.rootTake())


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
    _sync_parms_to_active_takes(node)


def on_toggle_change(node, parm_name, **_):
    """Do not allow the last ON toggle to be turned off."""
    values = _get_existing_values(node)
    if not values:
        node.parm(parm_name).set(1)
    _sync_parms_to_active_takes(node)


def active_takes(node):
    active = _get_existing_values(node)
    result = []
    for take in hou.takes.takes():
        if active.get(_to_parm_name(take.name())):
            result.append(take)
    return result
