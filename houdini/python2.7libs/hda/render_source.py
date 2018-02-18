"""Manage change of input node.

Currently only sets the label to indicate what type of
input, but later it may adjust other parts of the UI. For
example, We allow the user to select different renderers in
the software section, but if the input type changes here, to
Arnold say, then we can promt the user to revisit the
software section, or even deal with it automatically.

"""
import submit


def get_render_node(node):
    """Get connected render node."""
    inputs = node.inputs()
    if not inputs:
        return None
    return inputs[0]


def _get_render_type(input_node):
    """Display render type in the node header."""
    if not input_node:
        return "Please connect a source node"

    node_type = input_node.type().name()

    if node_type == 'ifd':
        return 'Mantra render'
    if node_type == 'arnold':
        return 'Arnold render'
    if node_type == 'rib':
        return 'Prman render'
    if node_type in ['output', 'filecache']:
        return 'Simulation'
    return 'Unknown'


def update_input_node(node):
    """Callback triggered every time a connection is made/broken."""
    render_type = _get_render_type(get_render_node(node))
    node.parm('render_type').set(render_type)
    submit.update_button_state(node)
