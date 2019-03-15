from conductor.native.lib.data_block import ConductorDataBlock

def handle_instance_type(obj, attr):
    label = attr.get_applied_preset_label()
    if label:
        obj.get_attribute("last_instance_type").set_string(label)


def _to_menu_item(item):
    """Convert instance_type object to tuple.

    Tuple has unique key and value pair needed to build the
    menu. e.g. ( "highmem_32", "32 core, 208GB Mem")
    """
    key = "%s_%s" % (item["flavor"], item["cores"])
    return (key, item["description"])


def update(obj, data_block):
    instance_types = data_block.instance_types()
    instance_type_att = obj.get_attribute("instance_type")
    instance_type_att.remove_all_presets()
    for i, p in enumerate(instance_types):
        instance_type_att.add_preset(_to_menu_item(p)[1], str(i))


