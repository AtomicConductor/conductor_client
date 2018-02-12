
"""Deal with various ways of specifying frame range.

Attributes:
    NUMBER_RE: (Regex) Catch a frame number
    RANGE_RE: (Regex) Catch a frame range with optional step
    XP (Enum): Specify that expressions are Python
"""

import re
import hou
import render_source

NUMBER_RE = re.compile(r"^\d+$")
RANGE_RE = re.compile(r"^(?:\d+-\d+(?:x\d+)?)+$")
XP = hou.exprLanguage.Python


def _replace_with_value(parm, value=None):
    """Overwrite a controlled parm with its evaluated value or a given value"""
    val = value or parm.eval()
    parm.deleteAllKeyframes()
    parm.set(val)


def _replace_with_input_expression(parm, input_path):
    """Write expression based on equivalent parm on input node"""
    parm.deleteAllKeyframes()
    parm.setExpression('ch("%s")' % input_path, XP, True)


def _set_explicit(node):
    """Remove expressions on all channels and replace with evaluated"""
    for parm in ['1', '2', '3']:
        _replace_with_value(node.parm('fs%s' % parm))


def _set_input(node):
    """Give all channels an expression to link the input node

    If no input node, then warn the user and defer to explicit for now.
    """
    input_node = render_source.get_render_node(node)
    if not input_node:
        hou.ui.displayMessage(title='Missing input node',
                              text="Please connect a source node and try again.",
                              severity=hou.severityType.ImportantMessage)
        node.parm("range_type").set('explicit')
        _set_explicit(node)
        return
    input_node_path = input_node.path()
    for parm in ['1', '2', '3']:
        _replace_with_input_expression(
            node.parm('fs%s' % parm), '%s/f%s' % (input_node_path, parm))


def _set_scene(node):
    """Give all channels an expression to link the scene settings"""
    node.parm('fs1').setExpression(
        'hou.playbar.timelineRange()[0]', XP, True)
    node.parm('fs2').setExpression(
        'hou.playbar.timelineRange()[1]', XP, True)
    node.parm('fs3').setExpression(
        'hou.playbar.frameIncrement()', XP, True)


def _set_custom(node):
    """When switching to custom, just validate existing input"""
    validate_custom_range(node)


def validate_custom_range(node, **kw):
    """Custom range spec must be reducible to a list of frames.

    Valid custom range spec consists of either numbers or ranges separated by commas.
    Ranges can have an optional step value indicated by 'x'.
    Example valid custom range spec: "120, 5, 26-76,19-23x4,   1000-2000, 3,9,"

    Side effect - also strips leading/trailing commas from input

    Args:
        node (hou.Node): The node   
    """
    result = True
    val = node.parm("custom_range").eval().strip(',')
    if not bool(val):
        result = False
    for part in [x.strip() for x in val.split(',')]:
        if not (NUMBER_RE.match(part) or RANGE_RE.match(part)):
            result = False
            break
    node.parm("custom_valid").set(result)
    node.parm("custom_range").set(val)


def set_type(node, **kw):
    """Switch between different types of frame specification.

    Explicit: make inputs settable directly
    Input: link to frame range set in render node
    Scene: link to frame range set in scene
    Custom: give a range spec

    Args:
        node (hou.Node): The node
    """
    funcs = {
        "explicit": _set_explicit,
        "input": _set_input,
        "scene": _set_scene,
        "custom": _set_custom
    }
    func = node.parm("range_type").eval()
    funcs[func](node)
