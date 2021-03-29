import logging
import os

from conductor.lib import common

logger = logging.getLogger(__name__)

def _get_ocio_search_path(config_filepath):
    '''
    Get the "search_path" value in the config file.
    Though an OCIO config file is yaml, it may have custom data types (yaml tags) defined within it
    which can prevent a succesful reading when using a simple yaml.load call. So we try two
    different approaches for reading the file:
        1. Use OpenColorIO api.  This library/tools may not be available on a client's machine.
        2. Use pyyaml to load the yaml file and use a custom yaml constructor to omit the yaml tags
           from being read.
    '''
    logger.debug("Reading OCIO config from: %s", config_filepath)
    try:
        import PyOpenColorIO
    except ImportError as e:
        logger.warning(e)
        logger.warning("Could not find PyOpenColorIO library.  Loading OCIO config via yaml loader")
        config = common.load_yaml(config_filepath, safe=True, omit_tags=True)
        return config.get("search_path")
    else:
        config = PyOpenColorIO.Config.CreateFromFile(config_filepath)
        return config.getSearchPath()
            
def parse_ocio_config_paths(config_filepath):
    '''
    Parse the given OCIO config file for any paths that we may be interested in (for uploads)

    For now, we'll keep this simple and simply scrape the "search_path" value in the config file.
    However, it's possible that additional attributes in the config will need to be queried.
    '''

    if not os.path.isfile(config_filepath):
        raise Exception("OCIO config file does not exist: %s" % config_filepath)

    paths = []

    search_path_str = _get_ocio_search_path(config_filepath)
    logger.warning("Could not find PyOpenColorIO library.  Resorting to basic yaml loading")
    config_dirpath = os.path.dirname(config_filepath)
    search_paths = search_path_str.split(os.pathsep)
    logger.debug("Resolving config seach paths: %s", search_paths)
    for path in search_paths:
        # If the path is relative, resolve it
        if not os.path.isabs(path):
            path = os.path.join(config_dirpath, path)
            logging.debug("Resolved relative path '%s' to '%s'", )

        if not os.path.isdir(path):
            logger.warning("OCIO search path does not exist: %s", path)
            continue
        logger.debug("adding directory: %s", path)
        paths.append(path)

    return paths + [config_filepath]