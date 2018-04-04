"""Manage download directory choice.

Attributes: OUTPUT_DIR_PARMS (dict): If the user has chosen to
derive the output directory automatically from the driver
node, we need to know the name of the parm that contains the
output path, which is different for each kind of node.
"""

import os
import hou


OUTPUT_DIR_PARMS = {
    "ifd": "vm_picture",
    "arnold": "ar_picture",
    "ris": "ri_display",
    "dop": "dopoutput",
    "output": "dopoutput",
    "geometry": 'sopoutput'
}


def _get_from_source(node):
    driver_node = hou.node(node.parm('source').evalAsString())
    driver_type = driver_node.type().name() if driver_node else ""
    if not driver_type:
        return
    parm_name = OUTPUT_DIR_PARMS.get(driver_type)
    if not parm_name:
        return
    path = driver_node.parm(parm_name).eval()
    return os.path.dirname(path)


def toggle(node, **_):
    if not node.parm("override_output_dir").eval():
        node.parm('output_directory').set(_get_from_source(node))


def get_directory(node):
    """Get the directory that will be made available for download.

    By default, try to derive the output directory from the
    output path in the driver node. Do this by looking up
    the parm name based on the driver node type in
    OUTPUT_DIR_PARMS. If its not a node we know about (or
    even if it is), the user can select to override and
    specify a directory manually. If in either case, no
    directory is specified we fall back to $JOB/render.
    """
    if node.parm('override_output_dir').eval():
        return node.parm('output_directory').eval()
    else:
        return _get_from_source(node)
