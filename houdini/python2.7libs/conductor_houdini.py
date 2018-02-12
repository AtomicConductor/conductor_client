"""Handle callbacks from the node.

This includes handling all actions from widgets, as well as
populating menus, initializing state and so on.

"""
import os
import hou
from hda import instance_types, projects, frame_spec, render_source, submit, software
reload(projects)
reload(instance_types)
reload(frame_spec)
reload(render_source)
reload(submit)
reload(software)

__version__ = '1.0.0'

MENUS = dict(
    machine_type=instance_types.populate,
    project=projects.populate
)


def populate_menu(node, parm, **kw):
    """Populate any menu dynamically.

    Delegate the job of constructing the list to functions
    specific to each menu. Houdini requires the kv pairs to
    be flattened into a list.

    Args:
        node (hou.Node): The node
        parm (hou.Parm): The menu parm

    Returns:
        List: A flat array from kv pairs [k0, v0, k1, v2, ... kn, vn]

    """
    try:
        return MENUS[parm.name()](node)
    except Exception as e:
        hou.ui.displayMessage(title='Error', text=str(e),
                              severity=hou.severityType.Error)


def foo(node, **kw):
    """Update the whole node.

    and add a newline before and after the summary of a one
    add a newline before and after the summary of a one

    """
    print ("hello goodbye")


def update_node_callback(node, **kw):
    """Update the whole node.

    We do this on creation/loading or manually.

    Args:
        node (hou.Node): The node

    """
    instance_types.fetch(node)
    projects.fetch(node)
    frame_spec.validate_custom_range(node)
    render_source.update_input_node(node)


def num_instances_callback(node, **kw):
    """Summary.

    Args:
        node (TYPE): Description
        **kw: Description

    """
    # update_estimated_cost(node)
    pass


def print_debug_callback(node, **kw):
    print("print_debug")


ACTIONS = dict(
    conductor_submit=submit.doit,
    num_instances=num_instances_callback,
    print_debug=print_debug_callback,
    update=update_node_callback,
    range_type=frame_spec.set_type,
    custom_range=frame_spec.validate_custom_range,
    detect_software=software.detect,
    choose_software=software.choose,
    clear_software=software.clear,
       
)


def action_callback(**kwargs):
    """Parameter callbacks.

    Lookup correct allback in `callbacks` registry
       using the parm_name kw arg.

    Args:
        **kwargs: Description

    """

    print kwargs
    try:
        ACTIONS[kwargs['parm_name']](**kwargs)
    except Exception as e:
        hou.ui.displayMessage(title='Error', text=str(e),
                              severity=hou.severityType.Error)


def on_input_changed_callback(node, **kw):
    """Summary.

    Args:
        node (TYPE): Description
        **kw: Description

    """
    render_source.update_input_node(node)


def on_created_callback(node, **kw):
    """Summary.

    Args:
        node (TYPE): Description
        **kw: Description

    """
    update_node_callback(node)


def on_loaded_callback(node, **kw):
    """Summary.

    Args:
        node (TYPE): Description
        **kw: Description

    """
    update_node_callback(node)
