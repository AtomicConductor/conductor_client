"""
Responds to events in the clarisse version section of the ConductorJob attribute editor.
"""
from conductor.native.lib import package_tree as pt


def update(obj, data_block):
    """
    Rebuilds the clarisse_version menu.

    Args:
        obj (ConductorJob): Item on which to rebuild menu.
        data_block (ConductorDataBlock): Singleton object containing software package data.
    """

    clarisse_version_att = obj.get_attribute("clarisse_version")
    tree_data = data_block.package_tree().tree
    names = sorted([str(pt.to_name(t)) for t in tree_data["children"]])
    for i, name in enumerate(names):
        clarisse_version_att.add_preset(name, str(i))
