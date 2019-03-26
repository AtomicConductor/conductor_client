from conductor.native.lib.data_block import ConductorDataBlock

 
def handle_project(obj, attr):
    label = attr.get_applied_preset_label()
    if label:
        obj.get_attribute("last_project").set_string(label)


def update(obj, data_block):
    projects = ConductorDataBlock(product="clarisse").projects()
    project_att = obj.get_attribute("project")
    project_att.remove_all_presets()
    for i, p in enumerate(projects):
        project_att.add_preset(str(p["name"]), str(i))

    # There may be a case where the index that was saved in the file
    # is different from the actual project the index referred to when
    # the scene was saved. In this case we can look at the stashed
    # project name and figure out what to do.
    #
