"""Manage selection and autodetection of software dependencies.

This module is concerned with the houdini UI. Any logic that
deals with the software tree should happen in the
software_data module

"""
 
import hou

from conductor.houdini.lib import data_block
from conductor.houdini.lib import software_data as swd
from conductor.houdini.hda import houdini_info

FOLDER_PATH = ("Software", "Available packages")

NO_HOST_PACKAGES = "No conductor packages have been selected"


def _get_field_names(ptg):
    """Get names of existing toggles."""
    folder = ptg.findFolder(FOLDER_PATH)
    return [t.name() for t in folder.parmTemplates()]

 
def _get_existing_paths(node):
    """Remember a map of exiting takes that are enabled."""
    paths = []
    num = node.parm("packages").eval()
    for i in range(num):
        index = i+1
        paths.append(node.parm("package_%d" % index).eval())
        # if path != NO_HOST_PACKAGES:
        #     paths.append(path)
    return paths
   

def _add_package_entries(node, new_paths):
    """Create new strings to contain packages."""
    paths = sorted(list(set(_get_existing_paths(node) + new_paths)))
    # if not len(paths):
    #     paths.append(NO_HOST_PACKAGES)
    node.parm("packages").set(0)
    node.parm("packages").set(len(paths))
    for i, path in enumerate(paths):
        index = i+1
        node.parm("package_%d" % index).set(path)
        node.parm("package_%d" % index).lock(True)

def clear(node, **_):
     node.parm("packages").set(0)
     # _add_package_entries(node, [])


def get_package_tree(node):
    return data_block.ConductorDataBlock(product="houdini").package_tree()
 


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

       
def _get_extra_env_vars(node):
    num = node.parm("environment_kv_pairs").eval()
    result = []
    for i in range(1, num + 1):
        is_exclusive = node.parm("env_excl_%d" % i).eval()
        result.append({
            "name": node.parm("env_key_%d" % i).eval(),
            "value": node.parm("env_value_%d" % i).eval(),
            "merge_policy": ["append", "exclusive"][is_exclusive]
        })
    return result

def get_environment(node):
    package_tree = get_package_tree(node)
    paths = _get_existing_paths(node)
    package_env = package_tree.get_environment(paths)
    extra_vars = _get_extra_env_vars(node)
    package_env.extend(extra_vars)
    return package_env


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
        message="Conductor packages",
        title="Package chooser",
        clear_on_cancel=True)
    paths = []
    for path in results:
        paths += swd.to_all_paths(path)
    _add_package_entries(node, paths)
    # _check_empty(node)



# def update_package_tree(node, **kw):
#     package_tree = get_package_tree(node, force_fetch=True)
        
    

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
 


def initialize(node):
    """Default software configuration"""
    node.parm("extra_upload_paths").set(5)
    node.parm("upload_1").set('$CONDUCTOR_HOUDINI/scripts/chrender.py')
    node.parm("upload_2").set('$CONDUCTOR_HOUDINI/lib/sequence.sequence.py')
    node.parm("upload_3").set('$CONDUCTOR_HOUDINI/lib/sequence.clump.py')
    node.parm("upload_4").set('$CONDUCTOR_HOUDINI/lib/sequence.progressions.py')
    node.parm("upload_5").set('$CONDUCTOR_HOUDINI/lib/sequence.__init__.py')

    node.parm("environment_kv_pairs").set(1)
    node.parm("env_key_1").set('PYTHONPATH')
    node.parm("env_value_1").set('$CONDUCTOR_HOUDINI/lib/sequence')
    node.parm("env_excl_1").set(0)

    detect(node)


