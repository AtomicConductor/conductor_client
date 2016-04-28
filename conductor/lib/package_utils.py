import logging
from pprint import pformat
import re

logger = logging.getLogger(__name__)

from conductor.lib import common

def merge_package_environments(packages, base_env=None):
    '''
    For the given conductor software packages, resolve and merge their environements
    int one single dictionary.

    Merge policies:
        append: appends values, separated by colons
        exclusive: indicates that
    '''
    env = dict(base_env or {})  # Make a copy of the dict. Don't want to alter original
    for package in packages:
#         logger.debug("package: %s", package)
        for env_variable in package.get("environment", []):
            name = env_variable["name"]
            value = env_variable["value"]
            merge_policy = env_variable["merge_policy"]

            ### APPEND ###
            if merge_policy == "append":
                env[name] = ":".join([env[name], value]) if  env.get(name) else value

            ### EXCLUSIVE ###
            elif merge_policy == "exclusive":
                if name in  env and env[name] != value:
                    raise Exception("Could not merge package environments due to "
                                    "difference in exclusive environment variable: %s "
                                    "(%s vs %s)\n"
                                    "Packages:\n\t%s" % (name,
                                                         env[name],
                                                         value,
                                                         "\n\t".join([pformat(p) for p in packages])))
                env[name] = value

            else:
                raise Exception("Got unexpected merge policy: %s" % merge_policy)
    return env


def merge_package_environment(package_environment, base_env=None):
    '''
    For the given conductor software packages, resolve and merge their environements
    int one single dictionary.
    
    Merge policies:
        append: appends values, separated by colons 
        exclusive: indicates that 
    '''
    env = dict(base_env or {})  # Make a copy of the dict. Don't want to alter original

    logger.debug("package_environment: %s", package_environment)
    for env_variable in package_environment:
        name = env_variable["name"]
        value = env_variable["value"]
        merge_policy = env_variable["merge_policy"]

        ### APPEND ###
        if merge_policy == "append":
            env[name] = ":".join([env[name], value]) if  env.get(name) else value

        ### EXCLUSIVE ###
        elif merge_policy == "exclusive":
            if name in  env and env[name] != value:
                raise Exception("Could not merge package environments due to "
                                "difference in exclusive environment variable: %s "
                                "(%s vs %s)" % (name,
                                                env[name],
                                                value))
            env[name] = value

        else:
            raise Exception("Got unexpected merge policy: %s" % merge_policy)
    return env





def get_matching_packages(software_info, packages):
    matched_packages = []

    package_info = dict(software_info)

    # Strip out None/empty values
    software_info = dict((k.lower(), v.lower()) for k, v in software_info.iteritems() if v not in [None, ""])

    for package in packages:
        if all(item in package.items() for item in package_info.items()):
            matched_packages.append(package)

    return matched_packages


def get_host_from_packages(cls, package, source_packages):
    '''
    If the given package has a host package, retrieve the host package from
    the app.
    '''
    plugin_host_product = package.get("plugin_host_product")

    # If no host package is required then simply return an empty dict
    if not plugin_host_product:
        return {}

    plugin_host_version = package["plugin_host_version"]


    '''
    If the given package has a host package, retrieve the host package from
    the app.
    '''
    print "source_packages", source_packages
    plugin_host_version = cls._cast_host_version(plugin_host_version)
    for package in source_packages:
#             logger.debug("Searching for host package in package: %s", package["package"])
        if package["product"] == plugin_host_product:
            print package["product"], package.get("major_version")
            if package.get("major_version") == plugin_host_version:
                return package

    raise Exception("Could not find host package: {} {}".format(plugin_host_product, plugin_host_version))



def get_host_package(host_product, host_version, strict=True):

    packages = common.get_package_ids() or {}
    if not packages:
        msg = "No packages found in resources file"
        logger.warning(msg)
        if strict:
            raise Exception(msg)

    product_versions = packages.get(host_product) or {}
    if not product_versions:
        msg = "No %s product versions found in resources file" % host_product
        logger.warning(msg)
        if strict:
            raise Exception(msg)

    product_package = product_versions.get(host_version) or {}
    if not product_package:
        msg = 'No %s version "%s"  found in resources file' % (host_product, host_version)
        logger.warning(msg)
        if strict:
            raise Exception(msg)
    return product_package


def get_plugin_package_id(host_product, host_version, plugin_product, plugin_version, strict=True):

    host_package = get_host_package(host_product, host_version, strict=strict) or {}

    plugin_versions = host_package.get(plugin_product) or {}
    if not plugin_versions:
        msg = 'No %s %s %s plugin versions found in resources file' % (host_product, host_version, plugin_product)
        logger.warning(msg)
        if strict:
            raise Exception(msg)

    plugin_package_id = plugin_versions.get(plugin_version)
    if not plugin_package_id:
        msg = 'No %s %s %s version "%s"  found in resources file' % (host_product, plugin_product, host_version, plugin_version)
        logger.warning(msg)
        if strict:
            raise Exception(msg)

    return plugin_package_id




class ProductInfo(object):
    '''
    A class for retrieving version information for a given piece of software.
    This is a baseclass that is intended to be overridden for each piece
    of software this is supported.

     # This is package for Maya
      {'product': 'Maya'
       'version': "Autodesk Maya 2015 SP4"
       'plugin_host_product': '',
       'plugin_host_version': ''},

     # This is a package for Arnold for Maya
      {'product': 'Arnold for Maya',
       'version': '1.1.1.1'
       'plugin_host_product': 'Maya',
       'plugin_host_version': '2015'}
    '''

    @classmethod
    def get_product(cls):
        '''
        Return the name of the software package, e.g. "Maya" or "Vray for Maya", or "Katana"
        '''
        raise NotImplementedError

    @classmethod
    def get_vendor(cls):
        '''
        Return the Product vendor name, e.g. "Autodesk"
        '''

    @classmethod
    def get_version(cls):
        '''
        Return the name of the software package, e.g. "Autodesk Maya 2015 SP4"
        '''
        NotImplementedError

    @classmethod
    def get_major_version(cls):
        '''
        Return the name of the software package, e.g. "Autodesk Maya 2015 SP4"
        '''
        return cls.regex_version().get("major_version", "")

    @classmethod
    def get_minor_version(cls):
        '''
        Return the name of the software package, e.g. "Autodesk Maya 2015 SP4"
        '''
        return cls.regex_version().get("minor_version", "")


    @classmethod
    def get_release_version(cls):
        '''
        Return the name of the software package, e.g. "Autodesk Maya 2015 SP4"
        '''
        return cls.regex_version().get("release_version", "")

    @classmethod
    def get_build_version(cls):
        '''
        Return the name of the software package, e.g. "Autodesk Maya 2015 SP4"
        '''
        return cls.regex_version().get("build_version", "")


    @classmethod
    def get_plugin_host_product(cls):
        '''
        Return the name of the host software package, e.g. "Maya" or "Katana"
        '''
        return ""

    @classmethod
    def get_plugin_host_version(cls):
        '''
        Return the name of the host software package, e.g. "Autodesk Maya 2015 SP4"
        '''
        return ""

    @classmethod
    def regex_version(cls):
        '''
        '''
        version_str = cls.get_version()
        match = re.match(cls.get_regex(), version_str)
        if not match:
            raise Exception("Unable regex product version string: %s", version_str)

        return match.groupdict()

    @classmethod
    def get_regex(cls):
        raise NotImplementedError


    @classmethod
    def get(cls, product=None, vendor=None, version=None, plugin_host_product=None, plugin_host_version=None):
        info = {}
        info["product"] = product if product != None else cls.get_product()
#         info["vendor"] = vendor if vendor != None else cls.get_vendor()
#         info["version"] = version if version != None else cls.get_version()
        info["major_version"] = version if version != None else cls.get_major_version()
        info["minor_version"] = version if version != None else cls.get_minor_version()
        info["release_version"] = version if version != None else cls.get_release_version()
        info["build_version"] = version if version != None else cls.get_build_version()
        info["plugin_host_product"] = plugin_host_product if plugin_host_product != None else cls.get_plugin_host_product()
        info["plugin_host_version"] = plugin_host_version if plugin_host_version != None else cls.get_plugin_host_version()
        return info
