"""Manage the list of takes to be rendered.

Most of the functions in this file are concerned with
building and refreshing the list of takes. We recurse down
the takes hierarchy to get the takes in the correct order
for a tree like display. Parm names are "take_<takename>"
because if they were simply <takename> there could be a name
clash. Each time we refresh, we delete all the old widgets
and rebuild, remembering any ON values. Unfortunately there
are no events emitted when takes are added or deleted, and
there is no way to detect if a tab changed in the param
group, so we have to provide a refresh button. ptg variable
is the parmTemplateGroup.

"""
from contextlib import contextmanager
import hou

FOLDER_PATH = ("Takes", "Render takes")

@contextmanager
def take_context(take):
    """Put houdini in the context of a take to run some code.

    I'm not sure if setting the same take causes a
    dependency update so so just in case, the take changing
    code only happens if we are not already on the desired
    take

    """
    current = hou.takes.currentTake()
    if current != take:
        hou.takes.setCurrentTake(take)
    yield
    if current != take:
        hou.takes.setCurrentTake(current)

def enable_for_current(node, *parm_tuple_names):
    """Enable parm dependencies for the current take.

    Some parms are automatically updated when other parms
    change. If the controlled parms are not included in the
    take then houdini throws an error. So any function that
    updates other parms should pass those parms' parm_tuple
    names to this function first.

    """
    parm_tuples = [node.parmTuple(name) for name in parm_tuple_names if node.parmTuple(name) ]
    take = hou.takes.currentTake()
    if not take == hou.takes.rootTake():
        for parm_tuple in parm_tuples:
            if not take.hasParmTuple(parm_tuple):
                take.addParmTuple(parm_tuple)

