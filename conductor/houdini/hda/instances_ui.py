"""Manage instance_type menu."""

import json
from conductor.houdini.lib import data_block


def _to_menu_item(item):
    """Convert instance_type object to tuple.

    Tuple has unique key and value pair needed to build the
    menu. e.g. ( "highmem_32", "32 core, 208GB Mem")
    """
    key = "%s_%s" % (item["flavor"], item["cores"])
    return (key, item["description"])


def populate_menu(node):
    """Populate instance type menu.

    Get list of items from the shared data_block where they
    have been cached. The menu needs a flat array: [k, v, k,
    v ....]
    """
    instance_types = data_block.ConductorDataBlock(
        product="houdini").instance_types()
    selected = node.parm('machine_type').eval()
    if selected not in (_to_menu_item(item)[0] for item in instance_types):
        node.parm('machine_type').set(_to_menu_item(instance_types[0])[0])

    return [k for i in instance_types for k in _to_menu_item(i)]
