import os
import re
import ix
from conductor.lib import package_utils


class ClarisseInfo(package_utils.ProductInfo):
    """Retrieve information about the current clarisse session."""

    @classmethod
    def get_product(cls):
        """e.g. clarisse."""
        return "clarisse"

    @classmethod
    def get_version(cls):
        """e.g. 3.5.SP1."""
        return ix.application.get_version_name().replace("_", ".")

    @classmethod
    def get_major_version(cls):
        """e.g. 3."""
        parts = ClarisseInfo.get_version().split(".")
        return parts[0] if len(parts) else None

    @classmethod
    def get_minor_version(cls):
        """e.g. 6."""
        parts = ClarisseInfo.get_version().split(".")
        return parts[1] if len(parts) > 1 else None

    @classmethod
    def get_release_version(cls):
        """e.g. SP1."""
        parts = ClarisseInfo.get_version().split(".")
        return parts[2] if len(parts) > 2 else None

    @classmethod
    def get_build_version(cls):
        parts = ClarisseInfo.get_version().split(".")
        return parts[3] if len(parts) > 3 else None

    @classmethod
    def get_vendor(cls):
        """isotropix make Clarisse."""
        return "isotropix"


class ClarissePluginInfo(package_utils.ProductInfo):
    """A class for retrieving version information about a plugin in clarisse.

    Should be subclassed. Will ultimately produce something like this:

     {'product': '<plugin name>',
      'major_version': u'3',
      'minor_version': u'00',
      'release_version': u'01',
      'build_version': '',
      'plugin_host_product': 'clarisse',
      'plugin_host_version': u'3.6'}
    """

    plugin_name = None

    @classmethod
    def get_product(cls):
        """Subclass must return product name."""
        raise NotImplementedError

    @classmethod
    def get_plugin_host_product(cls):
        """Return the name of the host software package.

        Example: "Clarisse".
        """
        return ClarisseInfo.get_product()

    @classmethod
    def get_plugin_host_version(cls):
        """Return the version of the host software package.

        Example: "Clarisse 16.5.323".
        """
        return ClarisseInfo.get_version()

    @classmethod
    def get_version(cls):
        """Return fully qualified name of the plugin.

        Derived class must override.
        """
        raise NotImplementedError

    @classmethod
    def exists(cls):
        """Return true if the plugin exists.

        Note this should be False if the definition exists but the
        plugin is not being used.
        """
        raise NotImplementedError

    @classmethod
    def get_regex(cls):
        """Derived class must provide a regex.

        The regex should extract the product and version parts
        """
        raise NotImplementedError
