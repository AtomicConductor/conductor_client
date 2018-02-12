import re
import hou
from conductor.lib import common


def _get_entries(path, ui_map):

    result = {}
    parts = path.split("/")
    host = parts[0]
    host_only = len(parts) == 1
    gid = "* %s" % ui_map[parts[0]][:8]
    result[gid] = parts[0]
    if not host_only:
        gid = "- %s" % ui_map[path][:8]
        result[gid] = parts[1]
    return result


def _to_ui_map(packages):
    result = {}
    hou_versions = packages.keys()
    for hou_version in hou_versions:
        gid = packages[hou_version]['package']
        hou_entry = "houdini-%s" % hou_version
        result[hou_entry] = gid

        tools = [p for p in packages[hou_version].keys()if not p == "package"]
        for tool in tools:
            tool_versions = packages[hou_version][tool].keys()
            for tool_version in tool_versions:
                gid = packages[hou_version][tool][tool_version]
                tool_entry = "%s/%s-%s" % (hou_entry, tool, tool_version)
                result[tool_entry] = gid
    return result


def choose(node, **kw):

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


def clear(node, **kw):
    empty = {}
    node.parm('software').set(empty)


def _get_current_package():
    hou_version = hou.applicationVersionString()
    path = "houdini-%s" % hou_version
    package = common.get_package_ids().get('houdini').get(hou_version)
    if not package:
        raise Exception(
            'Current houdini version (%s) is not available at Conductor' %
            hou_version)
    return (path, package)


def _detect_host():
    path, package = _get_current_package()
    package_id = package.get('package')
    gid_key = "* %s" % package_id[:8]
    return {gid_key: path}


def _plugins_for_host_package(package):
    result = {}
    tools = [p for p in package.keys() if not p == "package"]
    for tool in tools:
        versions = package[tool].keys()
        for version in versions:
            key = "%s-%s" % (tool, version)
            value = package[tool][version]
            result[key] = value
    print result
    return result

def _get_used_libraries():
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
    plugins = {}
    path, package = _get_current_package()
    available_plugins = _plugins_for_host_package(package)
    used_libraries = _get_used_libraries()
    for plugin in available_plugins.keys():
        regex = re.compile(plugin)
        for lib_path in used_libraries:
            if regex.search(lib_path):
                gid_key =  "- %s" % available_plugins[plugin][:8]
                plugins[gid_key] = plugin
                continue
    return plugins


def detect(node, **kw):

    host = _detect_host()
    plugins = _detect_plugins()

    software = node.parm('software').eval()
    software.update(host)
    software.update(plugins)
    node.parm('software').set(software)

    # plugins = {}
    # for category in hou.nodeTypeCategories().values():
    #     for node_type in category.nodeTypes().values():
    #         used = node_type.instances()
    #         if len(used):
    #             definition = node_type.definition()
    #             if definition is None:
    #                 continue
    #             path = definition.libraryFilePath()
    #             plugins.update(_detect_plugin)
    # if definition.libraryFilePath() not in result:
    # print definition.libraryFilePath()
    #             result.append(definition.libraryFilePath())
    # return result

    # files = hou.hda.loadedFiles()
    # for f in  files:
    #     print f

    # for res in tree_result:

    #     print res

    # >>> hou.applicationName()
    # 'houdini'
    # >>> hou.applicationPlatformInfo()
    # 'Darwin-17.0.0'
    # >>> hou.applicationVersion()
    # (16, 5, 323)
    # >>> hou.applicationVersionString()

    # hou.takes.takes()

    # arnold_node= hou.node("/out/arnold1")
    # t = arnold_node.type()
    # t.definition()
