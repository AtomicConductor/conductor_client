import os
import sys
from qtpy import uic
import PySide2.QtUiTools
from PySide2.QtUiTools import QUiLoader

from Qt import QtGui, QtCore, QtWidgets
import qtmodern.styles
import qtmodern.windows
import PySide2.QtWebEngineWidgets  # QWebEngineView()

from conductor.lib import pyside_utils, file_utils, common, exceptions, package_utils
from conductor.desktop.lib import module
from . import RESOURCES_DIRPATH


class WebModule(module.DesktopModule):
    _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'web.ui')

    def __init__(self, parent=None):

        super(WebModule, self).__init__(parent=parent)
#         r = PySide2.QtWebEngineWidgets.QWebEngineView()
#         print ("r", r)
#         r.load(QtCore.QUrl.fromLocalFile("/home/lschlosser/git/conductor_client_desktop/conductor/desktop/modules/home/resources/index.html"))
#         print ("r", r)

        uic.loadUi(self._ui_filepath, self)
#         uic.loadUi(self._ui_filepath, self)
        self.ui_webengineview.load(QtCore.QUrl("https://support.conductortech.com"))
        print ("self.ui_webengineview", self.ui_webengineview)

    def getNavbarVisible(self):
        return True

    def getNavbarName(self):
        return "Web Test"


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    qtmodern.styles.dark(app)
    submitter = WebModule()
    mw = qtmodern.windows.ModernWindow(submitter)
    mw.show()
    sys.exit(app.exec_())
