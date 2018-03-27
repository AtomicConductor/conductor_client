"""Summary.

Attributes:     HANDLER_MAP (dict): Mapping from a Houdini
definition description (such as Arnold) to a class to provide info for
the defined asset (such as ArnoldInfo).
"""
import os
import re
import hou
from conductor.lib import package_utils


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
        """sidefx make Houdini"""
        return "sidefx"


class HoudiniPluginInfo(package_utils.ProductInfo):
    """A class for retrieving version information about a plugin in houdini.

    Will ultimately produce something like this

     {'product': '<plugin name>',
      'major_version': u'3',
      'minor_version': u'00',
      'release_version': u'01',
      'build_version': '',
      'plugin_host_product': 'houdini',
      'plugin_host_version': u'16.5'}
    """

    plugin_name = None

    @classmethod
    def find_definition(cls):
        """Find the houdini definition for a plugin.

        Look at all node types that have instances in the
        scene and check the name of the otl against the name
        of this plugin, defined in the derived class.
        """
        otl = "/%s.otl" % cls.plugin_name
        for category in hou.nodeTypeCategories().values():
            for node_type in category.nodeTypes().values():
                if node_type.instances():
                    definition = node_type.definition()
                    if definition:
                        path = definition.libraryFilePath()
                        if path.endswith(otl):
                            return definition.libraryFilePath()
        return None

    @classmethod
    def get_product(cls):
        """Subclass must return product name."""
        raise NotImplementedError

    @classmethod
    def get_plugin_host_product(cls):
        """Return the name of the host software package.

        Example: "Houdini".
        """
        return HoudiniInfo.get_product()

    @classmethod
    def get_plugin_host_version(cls):
        """Return the version of the host software package.

        Example: "Houdini 16.5.323".
        """
        return HoudiniInfo.get_version()

    @classmethod
    def get_version(cls):
        """Return fully qualified name of the plugin.

        Derived class must override.
        """
        raise NotImplementedError

    @classmethod
    def exists(cls):
        """Return true if the plugin has a definition.

        Note this will be False if the definition exists but
        no instances exist.
        """
        return bool(cls.find_definition())

    @classmethod
    def get_regex(cls):
        """Derived class must provide a regex.

        The regex should extract the product and version
        parts
        """
        raise NotImplementedError


class ArnoldInfo(HoudiniPluginInfo):
    """A class for retrieving version information about the arnold plugin in
    Houdini.

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
        """The name that Conductor calls this plugin."""
        return "arnold-houdini"

    @classmethod
    def get_version(cls):
        """Get the full name and version of the plugin.

        This method name is a bit confusing. Its not just a
        version. It will return something like:
        'htoa-1.2.6.1'
        """
        path = cls.find_definition() or ""
        match = cls.get_regex().search(path)
        return match.group("version") if match else ""

    @classmethod
    def get_regex(cls):
        """Regex to extract parts form arnold plugin name.

        It is something like like 'htoa-1.2.6.1' where the
        last number (build version) is optional.  Note, this
        regex doubles up. It can extract the full versioned
        name from the library path (see get_version above),
        or it can extract individual version number parts
        from the versioned name
        """
        reg_parts = [
            r"(?P<version>htoa-",
            r"(?P<major_version>\d+)",
            r"(?:\.(?P<minor_version>\d+))?",
            r"(?:\.(?P<release_version>\d+))?",
            r"(?:\.(?P<build_version>\d+))?)"
        ]

        return re.compile("".join(reg_parts))


HANDLER_MAP = {
    "Arnold": ArnoldInfo
}


def get_plugin_definitions():
    """Get third party digital assets in use.

    Uses node_type.instances() to check that node is used in
    the scene, and path.startswith(os.environ["HFS"]) to
    filter out stuff that comes with Houdini. The return
    value is a list of houdini definitions.
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
    """Convert houdini definitions to Conductor info dicts.

    We use a mapping from the definition description (see
    HANDLER_MAP) in order to select the correct class to use
    to extract the name and version info so it interfaces
    with Conductor's package routines. The result is a list
    of dicts for used plugins.
    """
    result = []
    for definition in get_plugin_definitions():
        handler = HANDLER_MAP.get(definition.description())
        if handler:
            result.append(handler.get())
    return result
