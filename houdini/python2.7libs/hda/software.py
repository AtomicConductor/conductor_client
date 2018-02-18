import re
import hou
from conductor.lib import common


def _get_entries(path, ui_map):
    """Get possible entries from the given path.

    Path may contain one or 2 levels i.e. 'host/plugin' or just host.
    We look up the items from the map that comes from resources.yml to
    get the GID. The return is a dict with 1 or 2 entries to be displayed
    in the widget. host GID will be prefixed with *  and plugin GIDs are
    prefixed with -. For example, given the path some-host/some-plugin,

    return:
    {
        "*abcd1234": "some-host",
        "-4321dcba": "some-plugin"
    }

    """
    result = {}
    parts = path.split("/")
    host_only = len(parts) == 1
    gid = "* %s" % ui_map[parts[0]][:8]
    result[gid] = parts[0]
    if not host_only:
        gid = "- %s" % ui_map[path][:8]
        result[gid] = parts[1]
    return result


def _to_ui_map(packages):
    """Create a simple mapping from versioned software to ID.

    Software IDs structure in the resources.yml file is not
    suitable for houdini's tree chooser UI. So we concat
    name and version together, build hierarchy with "/"
    character. Each entry points to its guid. Example
    result:

    {
        houdini-16.5.323: "abcd12345678abcdabcd12345678abcd",
        houdini-16.5.323/htoa-2.2.2: "12345678abcdabcd12345678abcdabcd"
    }

    """
    result = {}
    hou_versions = packages.keys()
    for hou_version in hou_versions:
        gid = packages[hou_version]['package']
        hou_entry = "houdini-%s" % hou_version
        result[hou_entry] = gid

        tools = [p for p in packages[hou_version].keys() if not p == "package"]
        for tool in tools:
            tool_versions = packages[hou_version][tool].keys()
            for tool_version in tool_versions:
                gid = packages[hou_version][tool][tool_version]
                tool_entry = "%s/%s-%s" % (hou_entry, tool, tool_version)
                result[tool_entry] = gid
    return result


def _get_current_package():
    """Introspect to find the host software and check that Conductor knows
    about it.

    Return a tuple with a useful name like hoodini-16.5.323
    and the package object

    """
    hou_version = hou.applicationVersionString()
    versioned_name = "houdini-%s" % hou_version
    package = common.get_package_ids().get('houdini').get(hou_version)
    if not package:
        raise Exception(
            """Current houdini version (%s) is not available at Conductor.
            Please choose one manually.""" %
            hou_version)
    return (versioned_name, package)


def _detect_host():
    """Get host info and make a 32 bit id for display."""
    name, package = _get_current_package()
    package_id = package.get('package')
    gid_key = "* %s" % package_id[:8]
    return {gid_key: name}


def _plugins_for_host_package(package):
    """Generate kv pars of plugins in a package.

    A package is one host software from the rsources file
    and its available plugins. We turn it into a flat kv
    dict: {"plugin-version": "identifier"}

    """
    result = {}
    for tool in [p for p in package.keys() if not p == "package"]:
        versions = package[tool].keys()
        for version in versions:
            key = "%s-%s" % (tool, version)
            value = package[tool][version]
            result[key] = value
    return result


def _get_used_libraries():
    """Introspect session to find library paths for used node types."""
    result = []
    for category in hou.nodeTypeCategories().values():
        for node_type in category.nodeTypes().values():
            used = node_type.instances()
            if len(used):
                definition = node_type.definition()
                if definition is not None:
                    result.append(definition.libraryFilePath())
    return result


def _detect_plugins():
    """Find plugins in the scene that are available at conductor."""
    plugins = {}
    path, package = _get_current_package()
    available_plugins = _plugins_for_host_package(package)
    used_libraries = _get_used_libraries()
    for plugin in available_plugins.keys():
        regex = re.compile(plugin)
        for lib_path in used_libraries:
            if regex.search(lib_path):
                gid_key = "- %s" % available_plugins[plugin][:8]
                plugins[gid_key] = plugin
                continue
    return plugins


def choose(node, **kw):
    """Open a tree chooser with all possible software choices.

    Add the result to existing chosen software and set the
    param value.

    TODO - remove or warn on conflicting software versions

    """
    packages = common.get_package_ids().get('houdini')
    ui_map = _to_ui_map(packages)
    choices = [val for val in ui_map.keys()]

    paths = hou.ui.selectFromTree(
        choices,
        exclusive=False,
        message="Choose software",
        title="Chooser",
        clear_on_cancel=True)

    software = node.parm('software').eval()
    for path in paths:
        software.update(_get_entries(path, ui_map))
    node.parm('software').set(software)


def detect(node, **kw):
    """Autodetect host package and plugins used in the scene.

    Match them against versions available at Conductor.

    """
    host = _detect_host()
    plugins = _detect_plugins()
    software = node.parm('software').eval()
    software.update(host)
    software.update(plugins)
    node.parm('software').set(software)


def clear(node, **kw):
    """Clear all entries."""
    empty = {}
    node.parm('software').set(empty)
