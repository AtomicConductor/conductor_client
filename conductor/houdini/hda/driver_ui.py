"""Manage change of input node.

Currently only sets the label to indicate what type of
input, but later it may adjust other parts of the UI. For
example, We allow the user to select different renderers in
the software section, but if the input type changes here, to
Arnold say, then we can prompt the user to revisit the
software section, or even deal with it automatically.

"""
from conductor.houdini.hda import uistate


SIMULATION_NODES = ["dop", "geometry"]


def _get_nice_driver_type(input_type):
    """Display render type in the node header."""
    if not input_type:
        return "No render source"
    if input_type == 'ifd':
        return 'Mantra render'
    if input_type == 'arnold':
        return 'Arnold render'
    if input_type == 'ris':
        return 'Prman render'
    if input_type in SIMULATION_NODES:
        return 'Simulation'
    return input_type


def get_driver_node(node):
    """Get connected driver node."""
    inputs = node.inputs()
    return inputs[0] if inputs else None


def get_driver_type(node):
    input_node = get_driver_node(node)
    return input_node.type().name() if input_node else None

def is_simulation(node):
    return  get_driver_type(node) in SIMULATION_NODES
    

def update_input_node(node):
    """Callback triggered every time a connection is made/broken."""
    driver_node =  get_driver_node(node)
    path = driver_node.path() if driver_node else ""
    driver_type = get_driver_type(node)
    node.parm('driver_type').set(_get_nice_driver_type(driver_type))
    node.parm('source').set(path)
    uistate.update_button_state(node)
