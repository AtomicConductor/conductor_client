"""Manage change of input jobs for a submitter node."""
from conductor.houdini.hda import types, uistate


def update_inputs(node):
    """Callback triggered every time a connection is made/broken.

    When a node is added or removed, check it is a
    Conductor::job node and disconnect if not.
    """
    conns = node.inputConnections()
    for conn in conns:
        index = conn.inputIndex()
        if not types.is_job_node(conn.inputNode()):
            node.setInput(index, None, 0)
    uistate.update_button_state(node)
