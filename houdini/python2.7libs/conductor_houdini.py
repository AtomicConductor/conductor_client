import hou
from conductor import CONFIG
from conductor.lib import api_client
from hda_lib import instance_types, projects, frame_spec, render_source
reload(projects)
reload(instance_types)
reload(frame_spec)
reload(render_source)


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


menus = dict(
    machine_type=instance_types.populate,
    project=projects.populate
)


def populate_menu(node, parm, **_):
  return menus[parm.name()](node)


def update_node_callback(node, **_):
  instance_types.fetch(node)
  projects.fetch(node)
  frame_spec.validate_custom_range(node)
  render_source.update_input_node(node)


def conductor_submit_callback(node, **_):
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
  update_estimated_cost(node)


def print_debug_callback(node, **_):
  print("print_debug")
  print(get_projects())
  print(get_instance_types(node))


callbacks = dict(
    conductor_submit=conductor_submit_callback,
    num_instances=num_instances_callback,
    print_debug=print_debug_callback,
    update=update_node_callback,
    range_type=frame_spec.set_type,
    custom_range=frame_spec.validate_custom_range
)


def action_callback(**kwargs):
  """
  Parameter callbacks. 

  Lookup correct allback in `callbacks` registry
     using the parm_name kw arg.
  """
  try:
    callbacks[kwargs['parm_name']](**kwargs)
  except Exception as e:
    hou.ui.displayMessage(title='Error', text=str(e),
                          severity=hou.severityType.Error)


def on_input_changed_callback(node, **_):
  render_source.update_input_node(node)


def on_created_callback(node, **_):
  update_node_callback(node)


def on_loaded_callback(node, **_):
  update_node_callback(node)
