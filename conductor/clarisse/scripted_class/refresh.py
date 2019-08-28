"""
Module concerned with refreshing the datablock and the attribute editor.
"""

import ix
from conductor.clarisse.clarisse_info import ClarisseInfo
from conductor.clarisse.scripted_class import (
    debug_ui,
    frames_ui,
    instances_ui,
    projects_ui,
)
from conductor.native.lib.data_block import ConductorDataBlock


def force_ae_refresh(node):
    """
    Trigger an attribute editor refresh.
    
    Args:
        node (ConductorJob): item whose attrmibute editor to refresh.
    """
    attr = node.get_attribute("instance_type")
    count = attr.get_preset_count()
    applied = attr.get_applied_preset_index()
    if count:
        last = count - 1
        preset = (attr.get_preset_label(last), attr.get_preset_value(last))
        attr.remove_preset(last)
        attr.add_preset(preset[0], preset[1])
        attr.set_long(applied)


def refresh(_, **kw):
    """
    Respond to connect button click, and others that may benefit from a refresh.

    Update UI for projects and instances from the data block.
    
    Args:
        (kw["force"]): If true, invalidate the datablock and fetch fresh from
        Conductor. We update all ConductorJob nodes. Also update the log level
        in the UI.
    """

    kw["product"] = "clarisse"
    data_block = ConductorDataBlock(**kw)
    nodes = ix.api.OfObjectArray()
    ix.application.get_factory().get_all_objects("ConductorJob", nodes)

    host = ClarisseInfo().get()
    detected_host_paths = data_block.package_tree().get_all_paths_to(**host)

    for obj in nodes:

        projects_ui.update(obj, data_block)
        instances_ui.update(obj, data_block)
        frames_ui.update_frame_stats_message(obj)

        packages_attr = obj.get_attribute("packages")
        if not packages_attr.get_value_count():
            for path in detected_host_paths:
                packages_attr.add_string(path)

    debug_ui.refresh_log_level(nodes)
