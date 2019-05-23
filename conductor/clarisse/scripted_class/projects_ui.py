
def handle_project(obj, attr):
    """When project changes, stash its name on a string att.

    The current applied option is saved by its index. There may be a
    case where the index that was saved in the file is different from
    the actual project that the index referred to when the scene was
    saved, if new projects are added with a lower alphabetical position
    for example. In this case we can look at the stashed project name
    and figure out what to do. Note, the reassignment is not yet
    implemented, but the stashed name part is.
    """
    label = attr.get_applied_preset_label()
    if label:
        obj.get_attribute("last_project").set_string(label)


def update(obj, data_block):
    """Fetch projects afresh and repopulate menu."""
    projects = data_block.projects()
    project_att = obj.get_attribute("conductor_project_name")
    project_att.remove_all_presets()
    for i, project in enumerate(projects):
        project_att.add_preset(str(project["name"]), str(i))
