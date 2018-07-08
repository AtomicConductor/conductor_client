"""Access information about the connected driver inputs.

This module is only applicable to the Conductor::job
node, not the Conductor::submitter node, whose inputs are
jobs

Attributes:     SIMULATION_NODES (list): Node types to be
treated as sims.

get_driver_node: get the input driver node

get_driver_type: get the input driver type

is_simulation: is it a simuation

update_input_node: update UI when input connection changes
"""
from conductor.houdini.hda import uistate


SIMULATION_NODES = ["dop", "geometry"]


def _get_nice_driver_type(input_type):
    """Display nice render type info in the UI."""
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
    """Get the connected type name."""
    input_node = get_driver_node(node)
    return input_node.type().name() if input_node else None


def is_simulation(node):
    """Is the node to be treated as a simulation.

    This means the frame range will not be split into clumps
    and no frame spec UI will be shown.
    """
    return get_driver_type(node) in SIMULATION_NODES


def update_input_node(node):
    """Callback triggered every time a connection is made/broken.

    We update UI in 2 ways: 1. Show the type and the path to
    the input node. 2. Remove the frame range override
    section if the node is a simulation. While it may be
    possible that a user wants to sim an irregular set of
    frames, it is very unlikely and only serves to clutter
    the UI.
    """
    driver_node = get_driver_node(node)
    path = driver_node.path() if driver_node else ""
    driver_type = get_driver_type(node)
    node.parm('driver_type').set(_get_nice_driver_type(driver_type))
    node.parm('source').set(path)

    show_frames = not is_simulation(node)
    node.parm('show_frames_ui').set(show_frames)
    uistate.update_button_state(node)
