"""Handle callbacks and other actions from the node.

This includes handling all actions from widgets, aux buttons
as well as populating menus, initializing state and so on.

"""
import hou
from hda import instances, projects, frame_spec, render_source, submit, software, stats, notifications
reload(projects)
reload(instances)
reload(frame_spec)
reload(render_source)
reload(submit)
reload(software)
reload(stats)
reload(notifications)

__version__ = '1.0.0'

MENUS = dict(
    machine_type=instances.populate_menu,
    project=projects.populate_menu
)


def populate_menu(node, parm, **kw):
    """Populate a menu dynamically.

    Delegate the job of constructing the list of items.
    Houdini requires the token value pairs for menu item
    creation to be flattened into a flattened list like so:
    [k0, v0, k1, v2, ... kn, vn]

    """
    try:
        return MENUS[parm.name()](node)
    except Exception as e:
        hou.ui.displayMessage(title='Error', text=str(e),
                              severity=hou.severityType.Error)


def update_node_callback(node, **kw):
    """Initialize or update.

    We do this on creation/loading or manually.

    """
    instances.fetch_types(node)
    frame_spec.validate_custom_range(node)
    render_source.update_input_node(node)
    stats.update_estimates(node)
    frame_spec.set_type(node)
    notifications.validate_emails(node)
    notifications.email_hook_changed(node)

def show_request_callback(node, **kw):
    """Display the request info that will be sent to Conductor.

    Useful for checking validity and debugging

    """
    pass


ACTIONS = dict(
    submit=submit.doit,
    machine_type=instances.machine_type_changed,
    preemptible=instances.preemptible_changed,
    show_request=show_request_callback,
    update=update_node_callback,
    range_type=frame_spec.set_type,
    fs1=frame_spec.set_frame_range,
    fs2=frame_spec.set_frame_range,
    fs3=frame_spec.set_frame_range,
    custom_range=frame_spec.validate_custom_range,
    clump_size=frame_spec.set_clump_size,
    avg_frame_time=stats.avg_frame_time_changed,
    detect_software=software.detect,
    choose_software=software.choose,
    clear_software=software.clear,
    project=projects.select,
    email_addresses=notifications.validate_emails,
    email_on_submit=notifications.email_hook_changed,
    email_on_start=notifications.email_hook_changed,
    email_on_finish=notifications.email_hook_changed,
    email_on_failure=notifications.email_hook_changed
)

AUX_BUTTON_ACTIONS = dict(
    clump_size=frame_spec.best_clump_size
)


def action_button_callback(**kwargs):
    """Handle actions triggered by the little aux buttons next to params.

    Uses the parmtuple kw arg provided by houdini to
    differentiate.

    """
    try:
        AUX_BUTTON_ACTIONS[kwargs['parmtuple'].name()](**kwargs)
    except Exception as e:
        hou.ui.displayMessage(title='Error', text=str(e),
                              severity=hou.severityType.Error)


def action_callback(**kwargs):
    """Lookup callback in `CALLBACKS` registry.

    Uses the parm_name kw arg provided by houdini to
    differentiate.

    """
    try:
        ACTIONS[kwargs['parm_name']](**kwargs)
    except Exception as e:
        hou.ui.displayMessage(title='Error', text=str(e),
                              severity=hou.severityType.Error)


def on_input_changed_callback(node, **kw):
    """Make sure correct render source is displayed."""
    render_source.update_input_node(node)


def on_created_callback(node, **kw):
    """Initialize state when a node is created."""
    update_node_callback(node)


def on_loaded_callback(node, **kw):
    """Initialize state when a node is loaded."""
    update_node_callback(node)
