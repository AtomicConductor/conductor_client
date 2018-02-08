import hou

def get_render_node(node):
  inputs = node.inputs()
  if not inputs:
    return None
  return inputs[0]

def get_render_type(input_node):
  if input_node:
    input_node_type = input_node.type().name()
    if input_node_type == 'ifd':
      return 'Mantra render'
    elif input_node_type == 'arnold':
      return 'Arnold render'
    elif input_node_type == 'rib':
      return 'Prman render'
    elif input_node_type in ['output', 'filecache']:
      return 'Simulation'
  return "Please connect a source node"

def update_input_node(node):
  render_type = get_render_type(get_render_node(node))
  node.parm('render_type').set(render_type)
