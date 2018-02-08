import hou
from conductor.lib import common

def fetch(node):
  result = {}
  try:
    for i, obj in enumerate(common.get_conductor_instance_types()):
      result[str(i).zfill(2)] = obj['description']
    node.parm('machine_types').set(result)
    return result
  except Exception as e:
    hou.ui.displayMessage(title='Connection Error', text=str(e),   severity=hou.severityType.Error)
    return []

def populate(node):
  existing = node.parm('machine_types').eval()
  if bool(existing) == False:
    existing = fetch(node)
  return [item for pair in existing.iteritems() for item in pair]

 
 