from conductor import CONFIG
from conductor.lib import api_client


def fetch(node):
    """Fetch the list of projects and store them on projects param.

    If we don't do this, and instead fetch
    every time the menu is accessed, there is an unacceptable delay.

    Args:
        node (hou.Node): The node

    Returns:
        Dict: tokens and values to be use in menu creation
    """
    result = {}

    projects = CONFIG.get("projects") or api_client.request_projects()
    for i, obj in enumerate(projects):
        result[str(i).zfill(3)] = obj
    node.parm('projects').set(result)
    return result


def populate(node):
    """Populate project menu

    Get list from projects param where they are cached.

    Args:
      node (hou.Node): The node

    Returns:
      List: A flat array from kv pairs containing [k0, v0, k1, v2, ... kn, vn]
    """
    existing = node.parm('projects').eval()
    if not bool(existing):
        existing = fetch(node)
    return [item for pair in existing.iteritems() for item in pair] or []
