import hou
from conductor.lib import common
import re

number_re = re.compile("^\d+$")
range_re = re.compile("^(?:\d+-\d+(?:x\d+)?)+$")


def replace_with_value(parm, value=None):
  val = value or parm.eval()
  parm.deleteAllKeyframes()
  parm.set(val)


def replace_with_input_expression(parm, input_path):
  parm.deleteAllKeyframes()
  parm.setExpression('ch("%s")' % input_path, hou.exprLanguage.Python, True)


def set_explicit(node):
  for p in ['1', '2', '3']:
    replace_with_value(node.parm('fs%s' % p))


def set_input(node):
  msg ='Could not get frame range from a source node as none exists.'
  input_node_path = node.parm('source').evalAsString()
  if not input_node_path:
    raise Exception(msg)
  for p in ['1', '2', '3']:
    replace_with_input_expression(
        node.parm('fs%s' % p), '%s/f%s' % (input_node_path, p))


def set_scene(node):
  node.parm('fs1').setExpression(
      'hou.playbar.timelineRange()[0]', hou.exprLanguage.Python, True)
  node.parm('fs2').setExpression(
      'hou.playbar.timelineRange()[1]', hou.exprLanguage.Python, True)
  node.parm('fs3').setExpression(
      'hou.playbar.frameIncrement()', hou.exprLanguage.Python, True)


def set_custom(node):
  validate_custom_range(node)


funcs = {
    "explicit": set_explicit,
    "input": set_input,
    "scene": set_scene,
    "custom": set_custom
}


def set_type(node, **_):
  fn = node.parm("range_type").eval()
  funcs[fn](node)


def validate_custom_range(node, **_):
  result = True
  val = node.parm("custom_range").eval().strip(',')
  if not bool(val):
    result = False
  for part in [x.strip() for x in val.split(',')]:
    print(part)
    if not (number_re.match(part) or range_re.match(part)):
      result = False
      break
  node.parm("custom_valid").set(result)
  node.parm("custom_range").set(val)
