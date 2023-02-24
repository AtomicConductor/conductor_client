
from conductor.lib import maya_utils


def initializePlugin(plugin):
    maya_utils.load_conductor_menu()


def uninitializePlugin(plugin):
    maya_utils.unload_conductor_menu()
