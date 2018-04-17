"""Access information about the connected driver inputs.

This module is only applicable to the Conductor::job
node, not the Conductor::submitter node, whose inputs are
jobs.

Attributes:
    DRIVER_TYPES (dict): A mapping of information about input
    driver ROPs. human_name is used in the UI, and output_parm
    is used in the output_directory expression.
"""
import hou
from conductor.houdini.hda import frame_spec_ui, uistate

DRIVER_TYPES = {
    "ifd": {
        "human_name": "Mantra render",
        "output_parm": "vm_picture",
        "is_simulation": False
    },
    "baketexture::3.0": {
        "human_name": "Bake texture",
        "output_parm": "vm_uvoutputpicture1",
        "is_simulation": False
    },
    "arnold": {
        "human_name": "Arnold render",
        "output_parm": "ar_picture",
        "is_simulation": False
    },
    "ris": {
        "human_name": "Prman render",
        "output_parm": "ri_display",
        "is_simulation": False
    },
    "geometry": {
        "human_name": "Geometry cache",
        "output_parm": "sopoutput",
        "is_simulation": False
    },
    "output": {
        "human_name": "Simulation",
        "output_parm": "dopoutput",
        "is_simulation": True
    },
    "dop": {
        "human_name": "Simulation",
        "output_parm": "dopoutput",
        "is_simulation": True
    },
    "opengl": {
        "human_name": "OpenGL render",
        "output_parm": "picture",
        "is_simulation": False
    }
}


def human_name(input_type):
    """Human readable name for the UI.

    Example: ifd becomes Mantra render, dop becomes
    Simulation.
    """
    dt = DRIVER_TYPES.get(input_type)
    return dt["human_name"] if dt else "No driver source"


def output_parm(input_type):
    """Name of the parameter that holds the output path.

    The name is different for each type of Rop node, so we
    need to look it up in a map.
    """
    dt = DRIVER_TYPES.get(input_type)
    return dt and dt["output_parm"]


def is_simulation(input_type):
    """Is the source node to be treated as a simulation?

    This means the frame range will not be split into chunks
    and no frame spec UI will be shown.
    """
    dt = DRIVER_TYPES.get(input_type)
    return dt and dt["is_simulation"]


def _valid_driver(node):
    """Is the driver node valid.

    The user can in theory conect any node. However we can't
    currently render a node that has no frame range.
    Therefore we will use this to validate the input.

    TODO: Disconnect input connection attempt if invalid.
    """
    driver = get_driver_node(node)
    return driver and driver.parmTuple("f")


def get_driver_node(node):
    """Get connected driver node or None."""
    return hou.node(node.parm('source').evalAsString())


def get_driver_type(node):
    """Get the connected type name."""
    driver_node = get_driver_node(node)
    return driver_node.type().name() if driver_node else None


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
    node.parm('source').set(inputs[0].path() if connected else "")
    driver_type = get_driver_type(node)
    node.parm('driver_type').set(human_name(driver_type))
    node.parm('show_frames_ui').set(not is_simulation(driver_type))
    frame_spec_ui.set_type(node)
    uistate.update_button_state(node)
