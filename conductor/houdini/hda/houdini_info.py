from conductor.lib import package_utils
import os
import re
import hou


class HoudiniInfo(package_utils.ProductInfo):
    """Retrieve information about the current houdini session."""

    @classmethod
    def get_product(cls):
        """e.g. houdini."""
        return hou.applicationName()

    @classmethod
    def get_version(cls):
        """e.g. 16.5.323."""
        return hou.applicationVersionString()

    @classmethod
    def get_major_version(cls):
        """e.g. 16."""
        return str(hou.applicationVersion()[0])

    @classmethod
    def get_minor_version(cls):
        """e.g. 5."""
        return str(hou.applicationVersion()[1])

    @classmethod
    def get_release_version(cls):
        """e.g. 323."""
        return str(hou.applicationVersion()[2])

    @classmethod
    def get_build_version(cls):
        return ""

    @classmethod
    def get_vendor(cls):
        return "sidefx"


class HoudiniPluginInfo(package_utils.ProductInfo):
    """A class for retrieving version information about a plugin in hou.

    Will ultimately produce something like this

     {'product': '<plugin name>',
      'major_version': u'3',
      'minor_version': u'00',
      'release_version': u'01',
      'build_version': '',
      'plugin_host_product': 'maya',
      'plugin_host_version': u'2015'}

    """

    plugin_name = None

    @classmethod
    def find_definition(cls):
        otl = "/%s.otl" % cls.plugin_name
        for category in hou.nodeTypeCategories().values():
            for node_type in category.nodeTypes().values():
                if node_type.instances():
                    definition = node_type.definition()
                    if definition:
                        path = definition.libraryFilePath()
                        if path.endswith(otl):
                            return definition.libraryFilePath()

    @classmethod
    def get_product(cls):
        raise NotImplementedError

    @classmethod
    def get_plugin_host_product(cls):
        """Return the name of the host software package, e.g. "Maya" or
        "Katana"."""
        return HoudiniInfo.get_product()

    @classmethod
    def get_plugin_host_version(cls):
        """Return the name of the host software package, e.g. "Autodesk Maya
        2015 SP4"."""
        return HoudiniInfo.get_version()

    @classmethod
    def get_version(cls):
        raise NotImplementedError

    @classmethod
    def exists(cls):
        return cls.find_definition()

    @classmethod
    def get_regex(cls):
        raise NotImplementedError


class ArnoldInfo(HoudiniPluginInfo):
    """A class for retrieving version information about the arnold plugin in
    maya.

    Will ultimately produce something like this

     {'product': 'htoa',
      'major_version': u'1',
      'minor_version': u'2',
      'release_version': u'6',
      'build_version': u'1',
      'plugin_host_product': 'houdini',
      'plugin_host_version': u'16.5.323'}

    """
    plugin_name = "arnold_rop"

    @classmethod
    def get_product(cls):
        return "arnold-houdini"

    @classmethod
    def get_version(cls):
        path = cls.find_definition() or ""
        match = cls.get_regex().search(path)
        return match.group("version") if match else ""

    @classmethod
    def get_regex(cls):
        """'htoa-1.2.6.1' where build version is optional.

        Note, this regex doubles up. It can extract the full
        versioned name from the library path (see
        get_version above), or it can extract individual
        version number parts from the versioned name

        """

        return re.compile(
            r"(?P<version>htoa-(?P<major_version>\d+)(?:\.(?P<minor_version>\d+))?(?:\.(?P<release_version>\d+))?(?:\.(?P<build_version>\d+))?)")
 

HANDLER_MAP = {
    "Arnold": ArnoldInfo
}


def get_plugin_definitions():
    """Get third party digital assets in use.

    Uses node_type.instances() to check that node is used in
    the scene, and path.startswith(os.environ["HFS"]) to
    filter out stuff that comes wit Houdini.

    """
    result = []
    for category in hou.nodeTypeCategories().values():
        for node_type in category.nodeTypes().values():
            if node_type.instances():
                definition = node_type.definition()
                if definition:
                    path = definition.libraryFilePath()
                    if path and not path.startswith(os.environ["HFS"]):
                        result.append(definition)
    return result


def get_used_plugin_info():
    result = []
    for definition in get_plugin_definitions():
        handler = HANDLER_MAP.get(definition.description())
        if handler:
            result.append(handler.get())
    return result
