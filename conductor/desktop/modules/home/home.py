import os
import sys
from qtpy import uic
from Qt import QtGui, QtCore, QtWidgets
import qtmodern.styles
import qtmodern.windows
import PySide2.QtWebEngineWidgets  # QWebEngineView()


from conductor.lib import pyside_utils, file_utils, common, exceptions, package_utils
from conductor.desktop.lib import module
from . import RESOURCES_DIRPATH

# class HomeModule(module.DesktopModule):
#     _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'home.ui')
#
#     def __init__(self, parent=None):
#
#         super(HomeModule, self).__init__(parent=parent)
#         uic.loadUi(self._ui_filepath, self)
#
#     def getNavbarVisible(self):
#         return True
#
#     def getNavbarName(self):
#         return "Home"
#
#
# if __name__ == "__main__":
#
#     app = QtWidgets.QApplication(sys.argv)
#     qtmodern.styles.dark(app)
# #     submitter = DesktopConductorSubmitter()
#     submitter = HomeModule()
#     mw = qtmodern.windows.ModernWindow(submitter)
#     mw.show()
#     sys.exit(app.exec_())
#
#
#


class HomeModule(module.DesktopModule):
    _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'web.ui')

    def __init__(self, parent=None):

        super(HomeModule, self).__init__(parent=parent)
#         uic.loadUi(self._ui_filepath, self)
        uic.loadUi(self._ui_filepath, self)
#         r = PySide2.QtWebEngineWidgets.QWebEngineView()
#         print ("r", r)
#         r.load(QtCore.QUrl.fromLocalFile("/home/lschlosser/git/conductor_client_desktop/conductor/desktop/modules/home/resources/index.html"))
#         print ("r", r)
#         print ("self.ui_webengineview", self.ui_webengineview)
        self.ui_webengineview.load(QtCore.QUrl.fromLocalFile(os.path.join(RESOURCES_DIRPATH, "index.html")))
#         print ("self.ui_webengineview", self.ui_webengineview)
#         self.ui_webengineview.load(QtCore.QUrl("https://support.conductortech.com"))

    def getNavbarVisible(self):
        return True

    def getNavbarName(self):
        return "Home"


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    qtmodern.styles.dark(app)
    submitter = HomeModule()
    mw = qtmodern.windows.ModernWindow(submitter)
    mw.show()
    sys.exit(app.exec_())
