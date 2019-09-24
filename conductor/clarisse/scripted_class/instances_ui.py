"""
Responds to events in the machines section of the ConductorJob attribute editor.

NOTE: In a future version we will also save the name of the instance type. This
    is because the value is numeric, but the menu is built dynamically from the
    list of instance types. So by stashing the name we can try to repair it if
    the list changes order between sessions.

"""


def update(obj, data_block):
    """
    Rebuilds the instance types menu. 

    Args:
        obj (ConductorJob): Item on which to rebuild menu.
        data_block (ConductorDataBlock): Singleton object containing instance types.
    """

    instance_types = data_block.instance_types()
    instance_type_att = obj.get_attribute("instance_type")
    instance_type_att.remove_all_presets()
    for i, instance_type in enumerate(
        sorted(instance_types, key=lambda x: (x["cores"], x["memory"]))
    ):
        instance_type_att.add_preset(
            instance_type["description"].encode("utf-8"), str(i)
        )
