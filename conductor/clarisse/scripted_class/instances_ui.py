
def handle_instance_type(obj, attr):
    """When instance type changes, remember the string.

    This is because the value is numeric, but the menu is built
    dynamically from the list of instance types. So by stashing the name
    we can try to repair it if the list changes order between sessions.
    """
    label = attr.get_applied_preset_label()
    if label:
        obj.get_attribute("last_instance_type").set_string(label)


def _to_menu_item(item):
    """Convert instance_type object to tuple.

    Tuple has unique key and value pair needed to build the menu. e.g. (
    "highmem_32", "32 core, 208GB Mem")
    """
    key = "%s_%s" % (item["flavor"], item["cores"])
    return (key, item["description"])


def update(obj, data_block):
    """Rebuild the entire menu."""
    instance_types = data_block.instance_types()
    instance_type_att = obj.get_attribute("instance_type")
    instance_type_att.remove_all_presets()
    for i, instance_type in enumerate(instance_types):
        instance_type_att.add_preset(_to_menu_item(instance_type)[1], str(i))
