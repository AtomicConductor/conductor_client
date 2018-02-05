import glob
import hou
import os
import re
import sys
import webbrowser
 

__version__ = '1.0.0'


class JobCreationError(Exception):
  """Exception to handle problems while submiting job"""
  pass


class ParameterError(JobCreationError):
  """Exception to handle parameter validation error."""
  pass


class AbortedByUser(JobCreationError):
  """Exception to handle user action of canceling the submission."""
  pass

def populate_machine_type(node):
  # return [k for i in instances for k in (i[2], i[1])]
  return ["ma", "Machine A", "mb", "Machine B","mc", "Machine C",]

menu_callbacks = dict(machine_type=populate_machine_type)


def populate_menu(node, parm, **_):
  try:
    return menu_callbacks[parm.name()](node)
  except Exception as e:
    hou.ui.displayMessage(title='Connection Error', text=str(e),   severity=hou.severityType.Error)
    return []


def update_node_login(node):
  logged =  node.parm('logged_in').eval()
  node.parm('logged_in').set(int(not logged))
 
def get_render_node(node):
  input_node_path = node.parm('source').evalAsString()
  return hou.node(input_node_path)


def get_type_of_input_node(input_node):
  if input_node:
    input_node_type = input_node.type().name()
    if input_node_type == 'ifd':
      return 'Mantra'
    elif input_node_type == 'arnold':
      return 'Arnold'
    elif input_node_type in ['output', 'filecache']:
      return 'Simulation'
  return 'Unknown'


def update_input_node(node):
  print("update_input_node")

  node.parm('render_type').set(get_type_of_input_node(get_render_node(node)))

 
def login_callback(node, **_):
  print("login_callback")

  update_node_login(node)


def logout_callback(node, **_):
  print("logout_callback")

  update_node_login(node)
 
def conductor_submit_callback(node, **_):
  print("conductor_submit_callback")

  try:
    if hou.hipFile.hasUnsavedChanges():
      save_file_response = hou.ui.displayMessage(
          "There are some unsaved changes. Do you want to save the file before "
          "submitting to Conductor?", buttons=("Yes", "No", "Cancel"), close_choice=2)
      if save_file_response == 2:
        return
      if save_file_response == 0:
        hou.hipFile.save()
    hou.ui.displayMessage(text='Job submitted')
    print('Job submitted')
  except Exception as e:
    hou.ui.displayMessage(text=str(e), title='Job submission failed')


 
def num_instances_callback(node, **_):
  """Updates estimated cost of rendering.

  Args:
    node: hou.Node, Node calling the update.
    **_: Other parameters
  """
  update_estimated_cost(node)


def source_callback(node, **_):
  print("source_callback")
  update_input_node(node)

callbacks = dict(
    login=login_callback,
    logout=logout_callback,
    conductor_submit=conductor_submit_callback,
    num_instances=num_instances_callback,
    source=source_callback
)


def action_callback(**kwargs):
  kwargs['parm_name']
  hou.ui.displayMessage(text=kwargs['parm_name'], title='action_callback')

  """Callback hub for parameters. Callback is taken form `callback` registry
     using name of the parm.

  Args:
    **kwargs: Keyword parameters passed to the proper callback. Have to contain
              'parm_name' entry.
  """
  try:
    callbacks[kwargs['parm_name']](**kwargs)
  except Exception as e:
    hou.ui.displayMessage(title='Connection Error', text=str(e),
                          severity=hou.severityType.Error)


# Houdini node callbacks


def on_input_changed_callback(node, **_):

  inputs = node.inputs()
  print("on_input_changed_callback")

  if inputs:
    node.parm('source').set(inputs[0].path() )
  else:
     node.parm('source').set('')
  update_input_node(node)


def on_created_callback(node, **_):
  print("on_created_callback")

  update_node_login(node)


def on_loaded_callback(node, **_):
  print("on_loaded_callback")
  update_node_login(node)




# Traceback (most recent call last):
#   File "opdef:/conductor::Driver/submitter::0.1?OnLoaded", line 3, in <module>
#   File "/Users/julian/dev/conductor/houdini/python2.7libs/conductor_houdini.py", line 146, in on_loaded_callback
#     update_node_login(node)
#   File "/Users/julian/dev/conductor/houdini/python2.7libs/conductor_houdini.py", line 44, in update_node_login
#     hou.ui.displayMessage("update_node_login {}", node.parm('logged_in').eval())
#   File "/Applications/Houdini/Current/Frameworks/Houdini.framework/Versions/Current/Resources/houdini/python2.7libs/hou.py", line 46493, in displayMessage
#     return _hou.ui_displayMessage(*args, **kwargs)
# TypeError: in method 'ui_displayMessage', argument 3 of type 'std::vector<std::string,std::allocator<std::string > > const &'

