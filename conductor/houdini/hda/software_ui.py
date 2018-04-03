"""Manage software dependencies, extra uploads, and path additions.

There are 3 sections in the software tab in the UI:
1. Packages that Conductor knows about.
2. Extra upload paths for files such as user defined tools.
3. Amendments to environment that Conductor needs to know about.

Conductor packages are represented as paths, based on a DAG. e.g.
houdini `16.0.736/arnold-houdini 2.0.2.2/al-shaders 1.1`
See lib/package_tree module for more info

Attributes:
     NO_HOST_PACKAGES (str): Filler text when package list empty
"""

import hou

from conductor.houdini.lib import data_block
from conductor.houdini.lib import package_tree as ptree
from conductor.houdini.hda import houdini_info


NO_HOST_PACKAGES = "No conductor packages have been selected"


def _get_existing_paths(node):
    """Get the Conductor package paths currently in the UI."""
    paths = []
    num = node.parm("packages").eval()
    for i in range(num):
        paths.append(node.parm("package_%d" % (i + 1)).eval())
    return paths


def _add_package_entries(node, new_paths):
    """Add some paths to those that currently exist.

    The (hidden) packages parm controls the number of UI
    entries. Set it to 0 so existing entries are deleted,
    its easier than unlocking and replacing values. Then se
    to the new length, populate it with paths, then lock
    them as there's no reason the user should ever manually
    edit them.
    """
    paths = sorted(list(set(_get_existing_paths(node) + new_paths)))
    node.parm("packages").set(0)
    node.parm("packages").set(len(paths))
    for i, path in enumerate(paths):
        index = i + 1
        node.parm("package_%d" % index).set(path)
        node.parm("package_%d" % index).lock(True)


def _get_extra_env_vars(node):
    """Get a list of extra env vars from the UI.

    The items also have a merge_policy flag, which is used
    in compiling the final environment that will be sent to
    Conductor.
    """
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


def on_clear(node, **_):
    """Remove all packages when the clear button is pressed."""
    node.parm("packages").set(0)


def get_package_tree():
    """Get the package tree object from shared data.

    Note, the product keyword is only used when the
    singleton is first instantiated. Its probably redundant
    here.
    """
    return data_block.for_houdini().package_tree()


def get_chosen_ids(node):
    """Get package ids from the chosen package paths.

    Only the basename of each package is needed to find the
    package in the tree.
    """
    paths = _get_existing_paths(node)
    package_tree = get_package_tree()

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
    """Merge environments from packages and user defined sections.

    NOTE, package_tree.get_environment returns a
    package_environment object, which encapsulates a dict,
    but which can extend the dict based on the given merge
    policy for each entry.
    """
    package_tree = get_package_tree()
    paths = _get_existing_paths(node)
    package_env = package_tree.get_environment(paths)
    extra_vars = _get_extra_env_vars(node)
    package_env.extend(extra_vars)
    return package_env


def choose(node, **_):
    """Open a tree chooser with all possible software choices.

    Add the result to existing chosen software. When the
    user chooses a package below a host package, all
    ancestors are added. Although the chooser is multi-
    select, it has the annoying property that when you
    choose a node and a descendent, only the ancestor is
    returned.
    """

    package_tree = get_package_tree()
    choices = package_tree.to_path_list()
    results = hou.ui.selectFromTree(
        choices,
        exclusive=False,
        message="Conductor packages",
        title="Package chooser",
        clear_on_cancel=True)
    paths = []
    for path in results:
        paths += ptree.to_all_paths(path)
    _add_package_entries(node, paths)


def detect(node, **_):
    """Autodetect host package and plugins used in the scene.

    This will only find the package if Conductor knows about
    the exact version. Otherwise the user will have to use
    the chooser and select host and plugin versions that can
    hopefully manage the current scene. We may detect a
    plugin in the scene that Conductor knows about, but does
    not have a path-to-host that Conductor knows about. In
    this case it is considered unreachable and removed.
    Again, if the user wants it, they can select it manually
    along with the path-to-host that Conductor does know
    about.
    """

    package_tree = get_package_tree()

    host = houdini_info.HoudiniInfo().get()
    paths = package_tree.get_all_paths_to(**host)

    for info in houdini_info.get_used_plugin_info():
        plugin_paths = package_tree.get_all_paths_to(**info)
        paths += plugin_paths

    paths = ptree.remove_unreachable(paths)
    _add_package_entries(node, paths)


def initialize(node):
    """Populate extra upload paths and environment for chrender."""
    # node.parm("extra_upload_paths").set(5)
    # node.parm("upload_1").set(
    #     '$CONDUCTOR_LOCATION/conductor/houdini/scripts/chrender.py')
    # node.parm("upload_2").set(
    #     '$CONDUCTOR_LOCATION/conductor/houdini/lib/sequence.sequence.py')
    # node.parm("upload_3").set(
    #     '$CONDUCTOR_LOCATION/conductor/houdini/lib/sequence.clump.py')
    # node.parm("upload_4").set(
    #     '$CONDUCTOR_LOCATION/conductor/houdini/lib/sequence.progressions.py')
    # node.parm("upload_5").set(
    #     '$CONDUCTOR_LOCATION/conductor/houdini/lib/sequence.__init__.py')

    # node.parm("environment_kv_pairs").set(1)
    # node.parm("env_key_1").set('PYTHONPATH')
    # node.parm("env_value_1").set(
    #     '$CONDUCTOR_LOCATION/conductor/houdini/lib/sequence')
    # node.parm("env_excl_1").set(0)

    detect(node)
