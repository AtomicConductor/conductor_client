import ix
from conductor.clarisse.clarisse_info import ClarisseInfo
from conductor.clarisse.scripted_class import (frames_ui, instances_ui,
                                               projects_ui)
from conductor.native.lib.data_block import ConductorDataBlock


def force_ae_refresh(node):
    """Trigger an attribute editor refresh.

    The only way to force the attribute editor to refresh, it seems, is
    to remove and replace a preset in a long type attribute.
    """
    attr = node.get_attribute("instance_type")
    count = attr.get_preset_count()
    applied = attr.get_applied_preset_index()
    if count:
        last = count - 1
        preset = (
            attr.get_preset_label(last),
            attr.get_preset_value(last)
        )
        attr.remove_preset(last)
        attr.add_preset(preset[0], preset[1])
        attr.set_long(applied)


staticmethod


def refresh(_, **kw):
    """Respond to do_setup button click.

    Update UI for projects and instances from the data block. kwargs may
    contain the force keyword, which will invalidate the datablock and
    fetch fresh from Conductor. We may as well update all ConductorJob
    nodes.
    """
    kw["product"] = "clarisse"
    data_block = ConductorDataBlock(**kw)
    nodes = ix.api.OfObjectArray()
    ix.application.get_factory().get_all_objects("ConductorJob", nodes)

    host = ClarisseInfo().get()
    detected_host_paths = data_block.package_tree().get_all_paths_to(
        **host)

    for obj in nodes:

        projects_ui.update(obj, data_block)
        instances_ui.update(obj, data_block)
        frames_ui.update_frame_stats_message(obj)

        packages_attr = obj.get_attribute("packages")
        if not packages_attr.get_value_count():
            for path in detected_host_paths:
                packages_attr.add_string(path)
