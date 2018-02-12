"""Manage connection to the input render node
"""

def get_render_node(node):
    """Input node"""
    inputs = node.inputs()
    if not inputs:
        return None
    return inputs[0]



def _get_render_type(input_node):
    """String to display render type"""
    if input_node:
        input_node_type = input_node.type().name()
        if input_node_type == 'ifd':
            return 'Mantra render'
        elif input_node_type == 'arnold':
            return 'Arnold render'
        elif input_node_type == 'rib':
            return 'Prman render'
        elif input_node_type in ['output', 'filecache']:
            return 'Simulation'
    return "Please connect a source node"


def update_input_node(node):
    """Callback for every time a connection is made/broken 

    Args:
        node (hou.Node): The node
    """
    render_type = _get_render_type(get_render_node(node))
    node.parm('render_type').set(render_type)
