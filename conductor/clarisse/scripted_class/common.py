import os


def force_ae_refresh(node):
    """Trigger an attribute editor refresh.

    The only way to force the attribute editor to refresh it seems, is
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

