import os
import sys

from Qt import QtGui, QtCore, QtWidgets
import qtmodern.styles
import qtmodern.windows


import conductor
from conductor import submitter
from conductor.lib import pyside_utils
from conductor.desktop import modules

# This is a required import  so that when the .ui file is loaded, any
# resources that it uses from the qrc resource file will be found
from conductor import submitter_resources

from conductor.lib import pyside_utils, file_utils, common, exceptions, package_utils
from conductor.desktop.lib import module
# from . import RESOURCES_DIRPATH


class DesktopConductorSubmitter(submitter.ConductorSubmitter):
    '''

    This class inherits from the generic conductor submitter and adds an additional
    widget for maya-specific data.

    Note that the addional widget is stored (and accessible) via the
    self.extended_widget attribute

    When the UI loads it will automatically populate various information:
        1. Frame range
        2. Render layers (with their camera)

    '''

    _window_title = "Conductor - Maya"

    product = None

    def getSourceFilepath(self):
        return ""

    def _addExtendedWidget(self):
        pass

#     def getHostProductInfo(self):
#         return {
#             "product": None,
#             "version": None,
#             "package_id": None,
#         }

    def validateJobPackages(self):
        return True

    def filterPackages(self, show_all_versions=True):
        pass

    def autoPopulateJobPackages(self):
        return []

    def autoDetectPackageIds(self):
        return []


class SubmissionModule(DesktopConductorSubmitter, module.DesktopModule):
    #     _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'submission.ui')
    #
    #     def __init__(self, parent=None):
    #
    #         super(SubmissionModule, self).__init__(parent=parent)
    #         uic.loadUi(self._ui_filepath, self)

    def getNavbarVisible(self):
        return True

    def getNavbarName(self):
        return "Custom Submission"


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    qtmodern.styles.dark(app)
#     submitter = DesktopConductorSubmitter()
    submitter = SubmissionModule()
    mw = qtmodern.windows.ModernWindow(submitter)
    mw.show()
    sys.exit(app.exec_())
