import os
import sys

from Qt import QtGui, QtCore, QtWidgets
from PySide2 import QtQuickWidgets
import qtmodern.styles
import qtmodern.windows
from qtpy import uic

from conductor.lib import pyside_utils, file_utils, common, exceptions, package_utils
from conductor.desktop.lib import module
# from . import RESOURCES_DIRPATH
RESOURCES_DIRPATH = os.path.join(os.path.dirname(__file__), "resources")


class QtQuickModule(module.DesktopModule):
    _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'qtquick.ui')

    def __init__(self, parent=None):

        super(QtQuickModule, self).__init__(parent=parent)
        QtQuickWidgets.QQuickWidget()
        uic.loadUi(self._ui_filepath, self)
        print ("self.ui_qkwgt", self.ui_qkwgt)
#         self.ui_qkwgt.engine().quit.connect(QtCore.QCoreApplication.quit)
        self.ui_qkwgt.setSource(QtCore.QUrl(os.path.join(RESOURCES_DIRPATH, "maroon/maroon.qml")))
        print ("self.ui_qkwgt2", self.ui_qkwgt)

#         if (self.ui_qkwgt.status() == QQuickView.Error):
#             return -1

        self.ui_qkwgt.setResizeMode(self.ui_qkwgt.SizeRootObjectToView)


#         self.ui_qkwgt.setSource(QtCore.QUrl("/home/lschlosser/git/conductor_client_desktop/conductor/desktop/modules/qtquick/resources/view.qml"))

    def getNavbarVisible(self):
        return True

    def getNavbarName(self):
        return "QtQuick Test"


if __name__ == "__main__":
    #     QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QtWidgets.QApplication(sys.argv)
#     qtmodern.styles.dark(app)
    submitter = QtQuickModule()
#     mw = qtmodern.windows.ModernWindow(submitter)
#     mw.show()

    submitter.show()
    sys.exit(app.exec_())
