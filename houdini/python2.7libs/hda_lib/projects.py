import hou
from conductor import CONFIG
from conductor.lib import common, api_client


def fetch(node):
  """Do expensive menu item fetch once and cache items on node.projects k:v param."""
  result = {}
  try:
    projects = CONFIG.get("projects") or api_client.request_projects()
    for i, obj in enumerate(projects):
      result[str(i).zfill(3)] = obj
    node.parm('projects').set(result)
    return result
  except Exception as e:
    hou.ui.displayMessage(title='Connection Error', text=str(
        e),   severity=hou.severityType.Error)
    return {}


def populate(node):
  """Dynamically build menu items (flat array) from node.projects k:v param."""
  existing = node.parm('projects').eval()
  if bool(existing) == False:
    existing = fetch(node)
  return [item for pair in existing.iteritems() for item in pair]
