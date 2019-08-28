"""
Handles changes to log level from an attribute on any ConductorJob item.
"""
import ix
from conductor.lib import loggeria

LEVEL_LIST = [loggeria.LEVEL_MAP[key] for key in loggeria.LEVELS]


def handle_log_level(_, attr):
    """
    When a node changes log level, change all nodes log levels.
    
    Args:
        attr (OfAttr): Attribute that changed
    """
    nodes = ix.api.OfObjectArray()
    ix.application.get_factory().get_all_objects("ConductorJob", nodes)
    level_index = attr.get_long()
    level = loggeria.LEVELS[level_index]
    logger = loggeria.get_conductor_logger()
    logger.setLevel(level)
    for obj in nodes:
        obj.get_attribute("conductor_log_level").set_long(level_index)


def refresh_log_level(nodes):
    """
    On refresh resolve log level, update other nodes to reflect the same.
    
    Args:
        nodes (list): This is all ConductorJob nodes and we find the log level
        of the first one that is set.
    """
    logger = loggeria.get_conductor_logger()
    attrs = [obj.get_attribute("conductor_log_level") for obj in nodes]
    try:
        attr = next(
            attr for attr in attrs if attr.get_long() != loggeria.LEVELS.index("NOTSET")
        )
        handle_log_level(None, attr)
    except StopIteration:
        level = logger.getEffectiveLevel()
        level_index = LEVEL_LIST.index(level)
        for obj in nodes:
            obj.get_attribute("conductor_log_level").set_long(level_index)
