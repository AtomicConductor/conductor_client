"""Manage change of input node.

Currently only sets the label to indicate what type of
input, but later it may adjust other parts of the UI. For
example, We allow the user to select different renderers in
the software section, but if the input type changes here, to
Arnold say, then we can prompt the user to revisit the
software section, or even deal with it automatically.

"""
import uistate


def _get_nice_render_type(input_type):
    """Display render type in the node header."""
    if not input_type:
        return "No render source"
    if input_type == 'ifd':
        return 'Mantra render'
    if input_type == 'arnold':
        return 'Arnold render'
    if input_type == 'rib':
        return 'Prman render'
    if input_type in ['output', 'filecache']:
        return 'Simulation'
    return 'Unknown'


def get_render_node(node):
    """Get connected render node."""
    inputs = node.inputs()
    return inputs[0] if inputs else None


def get_render_type(node):
    input_node = get_render_node(node)
    return input_node.type().name() if input_node else None


def update_input_node(node):
    """Callback triggered every time a connection is made/broken."""
    render_node =  get_render_node(node)
    path = render_node.path() if render_node else ""
  
    render_type = get_render_type(node)
    print node.name()
    node.parm('render_type').set(_get_nice_render_type(render_type))
    node.parm('source').set(path)
    uistate.update_button_state(node)
