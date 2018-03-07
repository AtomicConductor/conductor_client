import copy
import json
import re
from conductor.lib.api_client import request_software_packages

# Display name regex.
# A lowercase product-name followed by a space followed by
# version which may be between 1 and 4 parts separated by
# dots.
DISPLAY_NAME_REGEX = re.compile(
    r"([a-z][a-z-]+)\s(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?")


def to_display_name(pkg):
    """Display name regex.

    A lowercase product name followed by a space followed by
    version which may be between 1 and 4 parts separated by
    dots.

    """
    version_parts = [
        pkg["major_version"],
        pkg["minor_version"],
        pkg["release_version"],
        pkg["build_version"]]
    version_string = (".").join([p for p in version_parts if p])
    return "%s %s" % (pkg["product"], version_string)


def to_info_dict(display_name):
    match = DISPLAY_NAME_REGEX.match(display_name)
    if match:
        product, major, minor, release, build = DISPLAY_NAME_REGEX.match(
            display_name).groups()
        return {
            "product": product,
            "major_version": major,
            "minor_version": minor,
            "release_version": release,
            "build_version": build
        }


def build_tree(packages, package):
    """Build a tree of dependent software plugins.

    For each ID in the `plugins` key, replace each with the
    package it refers to. Recurse until no more plugins are
    left.

    """
    pkg = light_copy(package)
    pkg["children"] = {}
    for child_id in package.get("plugins", []):
        child_package = next(
            (c for c in packages if c["package_id"] == child_id), None)
        if child_package:
            child_package = build_tree(
                packages, child_package)
            pkg["children"][child_package["package_id"]] = child_package
    return pkg


def light_copy(package):
    """Remove some unwanted keys."""
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


def is_product(tree, **kw):
    """Is this tree root the product described in kw.

    The root node has no `product` key because it is a
    collection of host packages.

    """
    if not tree.get("product"):
        return False
    for key, value in kw.iteritems():
        tree_value = tree[key]
        if value and value != tree_value:
            return False
    return True


def find_by_keys(tree, **kw):
    if not tree:
        return None
    if is_product(tree, **kw):
        return tree
    for child_tree in tree["children"].values():
        result = find_by_keys(child_tree, **kw)
        if result:
            return result
    return None


def find_by_path(tree, path, **kw):
    """"""
    with_ancestors = kw.get("with_ancestors", True)
    results = []
    for name in path.split("/"):
        kw = to_info_dict(name)
        tree = find_by_keys(tree, **kw)
        if tree.get("package_id"):
            results.append(tree)
    if not with_ancestors:
        results = [results[-1]]
    return results


def get_path_to(tree, **kw):
    name = to_display_name(tree) if tree.get("package_id") else ""
    if is_product(tree, **kw):
        return name
    for child_tree in tree["children"].values():
        res = get_path_to(child_tree, **kw)
        if res:
            return ("/").join([n for n in [name, res] if n])
    return None

    # new_path = "%s/%s" % (path, name)
    # for child_tree in tree["children"].values():
    #     child_name = get_path_to(child_tree, new_path, **kw):
    #     if name:


def to_path_list(tree, **kw):
    parent_name = kw.get("parent_name", "")
    paths = kw.get("paths", [])

    for child_tree in tree.get("children").values():
        name = ("/").join([n for n in [parent_name,
                                       to_display_name(child_tree)] if n])
        paths.append(name)
        paths = to_path_list(child_tree, paths=paths, parent_name=name)
    return paths


def to_all_paths(path):
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
        self._tree = build_tree(packages, {"plugins": root_ids})

    def find_by_keys(self, **kw):
        return find_by_keys(self._tree, **kw)

    def find_by_path(self, path, **kw):
        return find_by_path(self._tree, path, **kw)

    def get_path_to(self, **kw):
        return get_path_to(self.tree, **kw)

    def to_path_list(self):
        return to_path_list(self._tree)

    @property
    def tree(self):
        return self._tree

    def json(self):
        return json.dumps(self._tree)

    # def tree(version):


# s = PackageTree("houdini")
# print s.json()
# print s._product
