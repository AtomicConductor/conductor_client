"""Manage selection and autodetection of software dependencies.

This module is concerned with the houdini UI. Any logic that
deals with the software tree should happen in the
software_data module

"""

import re
import hou
from conductor.lib import common, api_client, package_utils
from conductor import CONFIG
import software_data as swd
import houdini_info

FOLDER_PATH = ("Software", "Packages")


def _get_field_names(ptg):
    """Get names of existing toggles."""
    folder = ptg.findFolder(FOLDER_PATH)

    return [t.name() for t in folder.parmTemplates()]


def _remove_package_entries(node):
    """Remove existing toggles in preparation to build new."""
    ptg = node.parmTemplateGroup()
    fields = _get_field_names(ptg)
    for field in fields:
        ptg.remove(field)
    node.setParmTemplateGroup(ptg)


def _get_existing_paths(node):
    """Remember a map of exiting takes that are enabled."""
    ptg = node.parmTemplateGroup()
    return [node.parm(name).eval() for name in _get_field_names(
        ptg) if name != "package_path_empty"]


def _create_label_when_empty():
    return hou.LabelParmTemplate(
        "package_path_empty",
        "No software packages selected")


def _create_entry_parm(path, index):
    name = "package_path_%d" % index
    return hou.StringParmTemplate(
        name, "", 1, default_value=path, is_label_hidden=True)


def _add_empty_entry(node):
    ptg = node.parmTemplateGroup()
    ptg.appendToFolder(FOLDER_PATH, _create_label_when_empty())
    node.setParmTemplateGroup(ptg)


def _add_package_entries(node, new_paths):
    """Create new strings to contain packages."""
    paths = sorted(list(set(_get_existing_paths(node) + new_paths)))
    _remove_package_entries(node)
    ptg = node.parmTemplateGroup()
    for i, path in enumerate(paths):
        ptg.appendToFolder(FOLDER_PATH, _create_entry_parm(path, i))
    node.setParmTemplateGroup(ptg)

    for i, path in enumerate(paths):
        parm = node.parm("package_path_%d" % i)
        parm.set(path)
        parm.lock(True)


def get_package_tree(node, force_fetch=False):
    """Get the software tree object."""
    cached_json = node.parm("softwares").eval()
    if cached_json and not force_fetch:
        sw = swd.PackageTree(json=cached_json)
    else:
        sw = swd.PackageTree(product="houdini")
        node.parm("softwares").set(sw.json())
    return sw


def get_chosen_ids(node):
    paths = _get_existing_paths(node)
    package_tree = get_package_tree(node)
    results = []
    for path in paths:
        name = path.split("/")[-1]
        package = package_tree.find_by_name(name)
        if package:
            package_id = package.get("package_id")
            if package_id:
                results.append(package_id)
    return results

def get_environment(node):
    
    package_tree = get_package_tree(node)
    config_environment = CONFIG.get("environment") or {}
    
    paths = _get_existing_paths(node)
    pkgs = [package_tree.find_by_path(path) for path in paths]
    return package_utils.merge_package_environments(pkgs,base_env=config_environment)


def choose(node, **_):
    """Open a tree chooser with all possible software choices.

    Add the result to existing chosen software and set the
    param value. When the user chooses a package below a host package, all ancestors are added. For this reason there is no need to run

    TODO - remove or warn on conflicting software versions

    """

    package_tree = get_package_tree(node)

    choices = package_tree.to_path_list()

    results = hou.ui.selectFromTree(
        choices,
        exclusive=False,
        message="Choose software",
        title="Chooser",
        clear_on_cancel=True)
    paths = []
    for path in results:
        paths += swd.to_all_paths(path)
    _add_package_entries(node, paths)



def update_package_tree(node, **kw):
    package_tree = get_package_tree(node, force_fetch=True)
    if not _get_existing_paths(node):
        detect(node)

def detect(node, **_):
    """Autodetect host package and plugins used in the scene.

    Create entries for those available at Conductor.

    """

    paths = []
    package_tree = get_package_tree(node)

    host = houdini_info.HoudiniInfo().get()
    host_paths = package_tree.get_all_paths_to(**host)
    paths += host_paths

    for info in houdini_info.get_used_plugin_info():
        plugin_paths = package_tree.get_all_paths_to(**info)
        paths += plugin_paths

    paths = swd.remove_unreachable(paths)

    _add_package_entries(node, paths)


def clear(node, **_):
    """Clear all entries."""
    _remove_package_entries(node)
    _add_empty_entry(node)
