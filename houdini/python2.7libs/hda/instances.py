"""Manage instance_type menu selection."""

from conductor.lib import common
import stats
import json


def _kv(item):
    """Convert instance_type object to tuple.

    Tuple has unique key and value pair needed to build the
    menu. e.g. ( "highmem_32", "32 core, 208GB Mem")

    """
    key = "%s_%s" % (item["flavor"], item["cores"])
    return (key, item["description"])


def fetch_types(node):
    """Fetch list of instance types.

    Store them on machine_types param as json so they can be
    accessed from the dynamic menu cretion script. If we
    don't do this, and instead fetch every time the menu is
    accessed, there is an unacceptable delay. Also check
    that the selected item in the menu is in the list. If it
    is not then set it to the first one in the list.

    """
    types = common.get_conductor_instance_types()
    node.parm('machine_types').set(json.dumps(types))
    selected = node.parm('machine_type').eval()

    if selected not in (_kv(item)[0] for item in types):
        node.parm('machine_type').set(_kv(types[0])[0])
    return types


def populate_menu(node):
    """Populate instance type menu.

    Get list from machine_types param where they have been
    cached. The menu needs a flat array: [k, v, k, v ....]

    """
    existing = json.loads(node.parm('machine_types').eval())
    if not bool(existing):
        existing = fetch_types(node)
    return [k for i in existing for k in _kv(i)]


def machine_type_changed(node, **kw):
    """Update estimates when machine type changes.

    Currently hidden

    """
    stats.update_estimates(node)


def preemptible_changed(node, **kw):
    """Update estimates when machine preemp type changes.

    Estimates currently hidden

    """
    stats.update_estimates(node)
