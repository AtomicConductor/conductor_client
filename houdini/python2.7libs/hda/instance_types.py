"""Manage instance_type selection
"""

from conductor.lib import common


def fetch(node):
    """Fetch the list of instance types and store them on machine_types param.

    If we don't do this, and instead fetch
    every time the menu is accessed, there is an unacceptable delay.

    Args:
        node (hou.Node): The node

    Returns:
        Dict: tokens and values to be use in menu creation
    """
    result = {}

    for i, obj in enumerate(common.get_conductor_instance_types()):
        result[str(i).zfill(2)] = obj['description']
    node.parm('machine_types').set(result)
    return result


def populate(node):
    """Populate instance type menu

    Get list from machine_types param where they are cached.

    Args:
        node (hou.Node): The node

    Returns:
        List: A flat array from kv pairs containing [k0, v0, k1, v2, ... kn, vn]
    """
    existing = node.parm('machine_types').eval()
    if not bool(existing):
        existing = fetch(node)
    return [item for pair in existing.iteritems() for item in pair]
