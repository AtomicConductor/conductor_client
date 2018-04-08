"""Access information about the connected driver inputs.

This module is only applicable to the Conductor::job
node, not the Conductor::submitter node, whose inputs are
jobs

Attributes:     SIMULATION_NODES (list): Node types to be
treated as sims.

"""
import hou

from conductor.houdini.hda import uistate, frame_spec_ui


SIMULATION_NODES = ["output", "dop"]
 
def _valid_driver(node):
    driver = get_driver_node(node)
    if not driver:
        return False
    for parm in ["f1", "f2", "f3"]:
        if not driver.parm(parm):
            return False
    return True


def _get_nice_driver_type(input_type):
    """Display nice render type info in the UI."""
    if not input_type:
        return "No render source"
    if input_type == 'ifd':
        return 'Mantra render'
    if input_type == 'baketexture::3.0':
        return 'Bake texture'
    if input_type == 'arnold':
        return 'Arnold render'
    if input_type == 'ris':
        return 'Prman render'
    if input_type == 'geometry':
        return 'Geometry cache'
    if input_type in SIMULATION_NODES:
        return 'Simulation'
    return input_type


def get_driver_node(node):
    """Get connected driver node or None."""
    return hou.node(node.parm('source').evalAsString())
 

def get_driver_type(node):
    """Get the connected type name."""
    driver_node = get_driver_node(node)
    return driver_node.type().name() if driver_node else None


def is_simulation(node):
    """Is the node to be treated as a simulation.

    This means the frame range will not be split into chunks
    and no frame spec UI will be shown.
    """
    return get_driver_type(node) in SIMULATION_NODES
 
def update_input_type(node, **_):
    driver_type = get_driver_type(node)
    node.parm('driver_type').set(_get_nice_driver_type(driver_type))
    show_frames = not is_simulation(node)
    node.parm('show_frames_ui').set(show_frames)
    frame_spec_ui.set_type(node)
    uistate.update_button_state(node)



def update_input_node(node):
    """Callback triggered every time a connection is made/broken.

    We update UI in 2 ways: 1. Show the type and the path to
    the input node. 2. Remove the frame range override
    section if the node is a simulation. While it may be
    possible that a user wants to sim an irregular set of
    frames, it is very unlikely and only serves to clutter
    the UI.
    """

    inputs = node.inputs()
    connected = inputs and inputs[0]
    node.parm('source').set(inputs[0].path() if connected else "" )
    update_input_type(node)

