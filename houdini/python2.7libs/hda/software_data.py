"""This module represents the list of software packages as a tree.

It has methods and functions to traverse the tree to find
packages and build paths etc.

"""


import copy
import json
import re
# from conductor.lib.api_client import request_software_packages
from tests.mocks.api_client_mock import request_software_packages


def remove_unreachable(paths):
    """Remove unreachable paths.

    Given some paths, remove those for which there are not
    additional paths present at each level up the hierarchy
    to the host. It is possible to have orphaned paths if a
    package can be reached by more than one path. For
    example, a shader library may be compatible with 2
    versions of a renderer, but only one of those renderers
    is compatible with this host. We need to remove the
    entry that references a different host.

    """
    results = []
    spaths = sorted(paths)
    previous = ""
    for path in spaths:
        parts = path.split("/")
        valid_subpath = path == "%s/%s" % (previous, parts[-1])
        if len(parts) == 1 or valid_subpath:
            results.append(path)
            previous = path
    return results


def to_name(pkg):
    """Name like `houdini 16.5.323` or `maya 2016.SP3`.

    This name is derived from the product and version fields
    in a package. It's purpose is to enable path
    construction to uniquely identify a package. For
    example: `houdini 16.0.736/arnold-houdini 2.0.2.2/al-
    shaders 1.0` Note: It is not necessarily possible to go
    the other way and extract those fields from the name.

    """
    version_parts = [
        pkg["major_version"],
        pkg["minor_version"],
        pkg["release_version"],
        pkg["build_version"]]
    version_string = (".").join([p for p in version_parts if p])
    return "%s %s" % (pkg["product"], version_string)


def _build_tree(packages, package):
    """Build a tree of dependent software plugins.

    For each ID in the `plugins` key, replace it with the
    package it refers to. Recurse until no more plugins are
    left.

    """
    pkg = _light_copy(package)
    pkg["children"] = {}
    for child_id in package.get("plugins", []):
        child_package = next(
            (c for c in packages if c["package_id"] == child_id), None)
        if child_package:
            child_package = _build_tree(
                packages, child_package)
            pkg["children"][child_package["package_id"]] = child_package
    return pkg


def _light_copy(package):
    """Remove some unwanted keys.

    TODO - Some of these may turn out to be wanted after all.

    """
    pkg = copy.deepcopy(package)
    for att in [
        "build_id",
        "time_updated",
        "description",
        "plugin_hosts",
        "updated_at",
        "time_created",
        "relative_path",
            "plugins"]:
        pkg.pop(att, None)

    return pkg


def _is_product(pkg, **kw):
    """Is this pkg the product described in kw.

    Works in one of 2 ways. Match against either 1. display
    name, or 2. the raw keys (product, major_version,
    minor_version, release_version, build_version). The root
    node has no `product` key because it is a collection of
    host packages.

    """
    if not pkg.get("product"):
        return False

    name = kw.get("name")
    if name:
        if name == to_name(pkg):
            return True
        return False

    for key, value in kw.iteritems():
        pkg_value = pkg[key]
        if value and value != pkg_value:
            return False
    return True


def _find_by_keys(tree, **kw):
    """Given product and version keys find the package."""
    if not tree:
        return None
    if _is_product(tree, **kw):
        return tree
    for child_tree in tree["children"].values():
        result = _find_by_keys(child_tree, **kw)
        if result:
            return result
    return None


def _find_by_name(branch, name, limit=None, depth=0):
    """Given a name made by `to_name` find the package.

    Name is typically part of a path.

    """
    if not branch:
        return None
    if _is_product(branch, name=name):
        return branch
    depth += 1
    if depth <= limit or not limit:
        for child_branch in branch["children"].values():
            result = _find_by_name(child_branch, name, limit, depth)
            if result:
                return result
    return None


def _find_by_path(tree, path):
    """Find the package uniquely described by this path.

    This method loops through parts of the path name and
    searches the tree for each part.  When it finds a
    matching package, we use that package as the root of the
    tree for the next search. As we are searching for an
    exact path match, we limit the search to one level deep
    each time.

    """

    result = None
    for name in [p for p in path.split("/") if p]:
        tree = _find_by_name(tree, name, 1)
        result = tree
    return result


def _to_path_list(tree, **kw):
    """Get paths to all nodes including roots.

    * 'houdini 16.0.736'
    * 'houdini 16.0.736/arnold-houdini 2.0.1'
    * 'houdini 16.0.736/arnold-houdini 2.0.1/al-shaders 1.0'

    """
    parent_name = kw.get("parent_name", "")
    paths = kw.get("paths", [])

    for child_tree in tree.get("children").values():
        name = ("/").join([n for n in [parent_name,
                                       to_name(child_tree)] if n])
        paths.append(name)
        paths = _to_path_list(child_tree, paths=paths, parent_name=name)
    return paths


def to_all_paths(path):
    """Extract all ancestor paths from a path.

    This can be useful if the user selects a plugin from a
    chooser, because we know we'll want its host ancestors.

    """
    result = []
    parts = path.split("/")
    while parts:
        result.append(("/").join(parts))
        parts.pop()
    result.reverse()
    return result


class PackageTree(object):

    def __init__(self, **kw):
        """Build tree from cached json or from name of a product.

        If json is given it is used. Otherwise build the
        tree with branches filtered by the name of the
        product. If the product is None then build from all
        root level packages (host softwares)

        """
        tree_json = kw.get("json")
        if tree_json:
            self._tree = json.loads(tree_json)
        else:
            product = kw.get("product")
            self._build_tree(product)

    def _build_tree(self, product):
        """Build from the name of the product.

        If the product is None, then build starting at all
        root level packages.

        """
        packages = request_software_packages()
        if product:
            root_ids = [p["package_id"]
                        for p in packages if p["product"] == product]
        else:
            root_ids = [p["package_id"]
                        for p in packages if not p["plugin_host_product"]]
        self._tree = _build_tree(packages, {"plugins": root_ids})

    def find_by_name(self, name, limit=None, depth=0):
        return _find_by_name(self._tree, name, limit, depth)

    def find_by_keys(self, **kw):
        return _find_by_keys(self._tree, **kw)

    def find_by_path(self, path):
        """Find the package uniquely described by this path."""
        return _find_by_path(self._tree, path)

    def to_path_list(self):
        """Get paths to all nodes."""
        return _to_path_list(self._tree)

    def get_all_paths_to(self, **kw):
        """All paths to the package described in kw.

        Its possible there is more than one path to a given
        node. For now we just get all paths through the tree
        and then select the ones whose leaf matches.

        """
        all_paths = _to_path_list(self._tree)
        name = to_name(kw)
        return [p for p in all_paths if p.endswith(name)]

#     def merge_environments(self, paths, base_env={}):
#         env = dict(base_env
#         for path in paths:
#             _find_by_path(self._tree, path)


# def merge_package_environments(packages, base_env=None):
#     '''
#     For the given conductor software packages, resolve and merge their environements
#     int one single dictionary.

#     Merge policies:
#         append: appends values, separated by colons
#         exclusive: indicates that
#     '''
#     env = dict(base_env or {})  # Make a copy of the dict. Don't want to alter original
#     for package in packages:
# #         logger.debug("package: %s", package)
#         for env_variable in package.get("environment", []):
#             name = env_variable["name"]
#             value = env_variable["value"]
#             merge_policy = env_variable["merge_policy"]

#             ### APPEND ###
#             if merge_policy == "append":
#                 env[name] = ":".join([env[name], value]) if  env.get(name) else value

#             ### EXCLUSIVE ###
#             elif merge_policy == "exclusive":
#                 if name in  env and env[name] != value:
#                     raise Exception("Could not merge package environments due to "
#                                     "difference in exclusive environment variable: %s "
#                                     "(%s vs %s)\n"
#                                     "Packages:\n\t%s" % (name,
#                                                          env[name],
#                                                          value,
#                                                          "\n\t".join([pformat(p) for p in packages])))
#                 env[name] = value

#             else:
#                 raise Exception("Got unexpected merge policy: %s" % merge_policy)
#     return env




    @property
    def tree(self):
        return self._tree

    def json(self):
        return json.dumps(self._tree)
