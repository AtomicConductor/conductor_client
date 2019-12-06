
import maya.cmds

build_menu_cmd = (
    '''
# Import full module path so not to conflict with user's other python packages (e.g. "maya_utils")
import conductor.lib.maya_utils

# build/load Conductor's menu
conductor.lib.maya_utils.build_conductor_menu()
'''
)

maya.cmds.evalDeferred(build_menu_cmd, lowestPriority=True)
