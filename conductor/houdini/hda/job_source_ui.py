"""Manage change of input node.

Currently only sets the label to indicate what type of
input, but later it may adjust other parts of the UI. For
example, We allow the user to select different renderers in
the software section, but if the input type changes here, to
Arnold say, then we can prompt the user to revisit the
software section, or even deal with it automatically.

"""
from conductor.houdini.hda import uistate, types

def get_job_nodes(node):
    return [n for n in node.inputs() if types.is_job_node(n)]


def update_inputs(node):
    """Callback triggered every time a connection is made/broken."""
    conns = node.inputConnections()
    for conn in conns:
        index = conn.inputIndex()
        if not _is_job_node(conn.inputNode()):
            node.setInput(index, None, 0)
    uistate.update_button_state(node)
