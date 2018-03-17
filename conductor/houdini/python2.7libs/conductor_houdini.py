"""Handle callbacks and other actions from the node.

This includes handling all actions from widgets, aux buttons
as well as populating menus, initializing state and so on.

"""
import traceback
import hou
from conductor.houdini.hda import (
    instances_ui,
    projects_ui,
    frame_spec_ui,
    render_source_ui,
    action_row_ui,
    software_ui,
    notifications,
    takes,
    uistate
)

 
def _update_node(node, **_):
    """Initialize or update.

    We do this on creation/loading or manually. We do it in
    the root take context to ensure everything is unlocked.

    """
    with takes.take_context(hou.takes.rootTake()):
        projects_ui.fetch(node)
        instances_ui.fetch_types(node)
        frame_spec_ui.validate_custom_range(node)
        frame_spec_ui.validate_scout_range(node)
        render_source_ui.update_input_node(node)
        frame_spec_ui.set_type(node)
        notifications.validate_emails(node)
        notifications.email_hook_changed(node)
        software_ui.update_package_tree(node)
        uistate.update_button_state(node)

MENUS = dict(
    machine_type=instances_ui.populate_menu,
    project=projects_ui.populate_menu
)
 
ACTIONS = dict(
    dry_run=action_row_ui.dry_run,
    preview=action_row_ui.preview,
    local_test=action_row_ui.local,
    submit=action_row_ui.doit,
    update=_update_node,
    use_custom=frame_spec_ui.set_type,
    fs1=frame_spec_ui.set_frame_range,
    fs2=frame_spec_ui.set_frame_range,
    fs3=frame_spec_ui.set_frame_range,
    custom_range=frame_spec_ui.validate_custom_range,
    clump_size=frame_spec_ui.set_clump_size,
    do_scout=frame_spec_ui.do_scout_changed,
    scout_frames=frame_spec_ui.validate_scout_range,
    detect_software=software_ui.detect,
    choose_software=software_ui.choose,
    clear_software=software_ui.clear,
    project=projects_ui.select,
    email_addresses=notifications.validate_emails,
    email_on_submit=notifications.email_hook_changed,
    email_on_start=notifications.email_hook_changed,
    email_on_finish=notifications.email_hook_changed,
    email_on_failure=notifications.email_hook_changed,
)

AUX_BUTTON_ACTIONS = dict(
    clump_size=frame_spec_ui.best_clump_size
)


def populate_menu(node, parm, **_):
    """Populate a menu dynamically.

    Houdini requires the token value pairs for menu item
    creation to be a flattened list like so: [k0, v0, k1,
    v2, ... kn, vn]

    """
    try:
        return MENUS[parm.name()](node)
    except hou.Error as err:
        hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
                              details_label="Show stack trace",
                              details=traceback.format_exc(),
                              severity=hou.severityType.Error)


def action_callback(**kwargs):
    """Lookup callback in `ACTIONS` registry.

    Uses the parm_name kw arg provided by houdini to
    differentiate.

    """
    try:
        ACTIONS[kwargs['parm_name']](**kwargs)
    except hou.InvalidInput as err:
        hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
                              details_label="Show stack trace",
                              details=traceback.format_exc(),
                              severity=hou.severityType.ImportantMessage)
    except hou.Error as err:
        hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
                              details_label="Show stack trace",
                              details=traceback.format_exc(),
                              severity=hou.severityType.Error)

    except(TypeError, ValueError) as err:
        hou.ui.displayMessage(title='Error', text=str(err),
                              details_label="Show stack trace",
                              details=traceback.format_exc(),
                              severity=hou.severityType.Error)

    except(Exception) as err:
        hou.ui.displayMessage(title='Error', text=str(err),
                              details_label="Show stack trace",
                              details=traceback.format_exc(),
                              severity=hou.severityType.Error)


def action_button_callback(**kwargs):
    """Handle actions triggered by the little buttons next to params.

    Uses the parmtuple kw arg provided by houdini to
    determine the parm this button refers to.

    """
    try:
        AUX_BUTTON_ACTIONS[kwargs['parmtuple'].name()](**kwargs)
    except hou.Error as err:
        hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
                              details_label="Show stack trace",
                              details=traceback.format_exc(),
                              severity=hou.severityType.Error)


def on_input_changed_callback(node, **_):
    """Make sure correct render source is displayed."""
    try:
        render_source_ui.update_input_node(node)
    except hou.Error as err:
        hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
                              details_label="Show stack trace",
                              details=traceback.format_exc(),
                              severity=hou.severityType.Error)


def on_created_callback(node, **_):
    """Initialize state when a node is created."""
    try:
        _update_node(node)
    except hou.Error as err:
        hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
                              details_label="Show stack trace",
                              details=traceback.format_exc(),
                              severity=hou.severityType.Error)


def on_loaded_callback(node, **_):
    """Initialize state when a node is loaded."""
    try:
        _update_node(node)
    except hou.Error as err:
        hou.ui.displayMessage(title='Error', text=err.instanceMessage(),
                              details_label="Show stack trace",
                              details=traceback.format_exc(),
                              severity=hou.severityType.Error)
