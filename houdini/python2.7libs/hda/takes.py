import hou

FOLDER_PATH = ("Takes", "Render takes")

def _takes_with_depth(take, depth, result):
    result.append((take.name(), depth))
    depth = depth + 1
    for child in take.children():
        _takes_with_depth(child, depth, result)


def get_takes_with_depth():
    result = []
    _takes_with_depth(hou.takes.rootTake(), 0, result)
    return result


def _get_toggles(ptg):
    folder = ptg.findFolder(FOLDER_PATH)
    return [t.name() for t in folder.parmTemplates()
            if t.type().name() == "Toggle"]


def _remove_toggles(node):
    ptg = node.parmTemplateGroup()
    toggles = _get_toggles(ptg)
    for toggle in toggles:
        ptg.remove(toggle)
    node.setParmTemplateGroup(ptg)


def _add_toggles(node, takes):
    ptg = node.parmTemplateGroup()
    for take in takes:
        name, depth = take
        prefix = ("- " * (depth))
        label = "%s%s" % (prefix, name)
        ptg.appendToFolder(FOLDER_PATH, hou.ToggleParmTemplate(name, label))
    node.setParmTemplateGroup(ptg)


def _get_existing_vals(node):
    ptg = node.parmTemplateGroup()
    names = _get_toggles(ptg)
    result = {}
    for name in names:
        val = node.parm(name).eval()
        if val:
            result[name] = val
    return result


def _set_values(node, values):
    for key, value in values.iteritems():
        if (node.parm(key)):
            node.parm(key).set(value)

def update_takes(node, **kw):
    takes = get_takes_with_depth()
    values = _get_existing_vals(node)
    _remove_toggles(node)
    _add_toggles(node, takes)
    if not values:
        values["Main"] = 1
    _set_values(node, values)

