"""Some utility functions when working in other takes."""
from contextlib import contextmanager

import hou


@contextmanager
def take_context(take):
    """Put houdini in the context of a take to run some code.

    This is handy for updating parms that might be locked on
    the current take. In this case we switch to the main
    take for a moment, do the update, and then switch back.
    I'm not sure if setting to the current take causes a
    dependency update so so just in case, the take changing
    code only happens if we are not already on the desired
    take.
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
    take then houdini throws an error because it can't
    change a locked parm. So any function that updates other
    parms should pass those parms' parm_tuple names to this
    function first.
    """
    parm_tuples = [node.parmTuple(name)
                   for name in parm_tuple_names if node.parmTuple(name)]
    take = hou.takes.currentTake()
    if not take == hou.takes.rootTake():
        for parm_tuple in parm_tuples:
            if not take.hasParmTuple(parm_tuple):
                take.addParmTuple(parm_tuple)
