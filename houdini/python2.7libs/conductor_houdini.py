"""Handle callbacks and other actions from the node.

This includes handling all actions from widgets, aux buttons
as well as populating menus, initializing state and so on.

"""

import hou
from hda import (
    instances,
    projects,
    frame_spec,
    render_source,
    submit,
    software,
    notifications,
    takes
)


def _update_node(node, **_):
    """Initialize or update.

    We do this on creation/loading or manually. We do it in
    the root take context to ensure everything is unlocked.

    """
    with takes.take_context(hou.takes.rootTake()):
        projects.fetch(node)
        instances.fetch_types(node)
        frame_spec.validate_custom_range(node)
        frame_spec.validate_scout_range(node)
        render_source.update_input_node(node)
        frame_spec.set_type(node)
        notifications.validate_emails(node)
        notifications.email_hook_changed(node)
        takes.update_takes(node)
        software.update_package_tree(node)
        submit.update_button_state(node)


MENUS = dict(
    machine_type=instances.populate_menu,
    project=projects.populate_menu
)

ACTIONS = dict(
    submit=submit.doit,
    show_request=submit.show_request,
    update=_update_node,
    range_type=frame_spec.set_type,
    fs1=frame_spec.set_frame_range,
    fs2=frame_spec.set_frame_range,
    fs3=frame_spec.set_frame_range,
    custom_range=frame_spec.validate_custom_range,
    clump_size=frame_spec.set_clump_size,
    do_scout=frame_spec.do_scout_changed,
    scout_frames=frame_spec.validate_scout_range,
    detect_software=software.detect,
    choose_software=software.choose,
    clear_software=software.clear,
    project=projects.select,
    email_addresses=notifications.validate_emails,
    email_on_submit=notifications.email_hook_changed,
    email_on_start=notifications.email_hook_changed,
    email_on_finish=notifications.email_hook_changed,
    email_on_failure=notifications.email_hook_changed,
    update_takes=takes.update_takes
)

AUX_BUTTON_ACTIONS = dict(
    clump_size=frame_spec.best_clump_size
)


def populate_menu(node, parm, **_):
    """Populate a menu dynamically.

    Delegate the job of constructing the list of items.
    Houdini requires the token value pairs for menu item
    creation to be a flattened list like so: [k0, v0, k1,
    v2, ... kn, vn]

    """
    try:
        return MENUS[parm.name()](node)
    except hou.Error as err:
        hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
                              severity=hou.severityType.Error)


def action_callback(**kwargs):
    """Lookup callback in `ACTIONS` registry.

    Uses the parm_name kw arg provided by houdini to
    differentiate.

    """
    ACTIONS[kwargs['parm_name']](**kwargs)
    # try:
    #     ACTIONS[kwargs['parm_name']](**kwargs)
    # except hou.InvalidInput as err:
    #     hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
    #                           severity=hou.severityType.ImportantMessage)
    # except hou.Error as err:
    #     hou.ui.displayMessage(title='Warning', text=err.instanceMessage(),
    #                           severity=hou.severityType.Error)

    # except(TypeError, ValueError) as err:
    #     hou.ui.displayMessage(title='Error', text=str(err),
    #                           severity=hou.severityType.Error)

    # except(Exception) as err:
    #     hou.ui.displayMessage(title='Error', text=str(err),
    #                           severity=hou.severityType.Error)


def action_button_callback(**kwargs):
    """Handle actions triggered by the little buttons next to params.

    Uses the parmtuple kw arg provided by houdini to
    differentiate.

    """
    try:
        AUX_BUTTON_ACTIONS[kwargs['parmtuple'].name()](**kwargs)
    except hou.Error as err:
        hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
                              severity=hou.severityType.Error)


def takes_callback(**kwargs):
    """Handle changes in dynamic `takes` toggles."""
    try:
        takes.on_toggle_change(**kwargs)
    except hou.Error as err:
        hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
                              severity=hou.severityType.Error)


def on_input_changed_callback(node, **_):
    """Make sure correct render source is displayed."""
    try:
        render_source.update_input_node(node)
    except hou.Error as err:
        hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
                              severity=hou.severityType.Error)


def on_created_callback(node, **_):
    """Initialize state when a node is created."""
    try:
        _update_node(node)
    except hou.Error as err:
        hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
                              severity=hou.severityType.Error)


def on_loaded_callback(node, **_):
    """Initialize state when a node is loaded."""
    try:
        _update_node(node)
    except hou.Error as err:
        hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
                              severity=hou.severityType.Error)
