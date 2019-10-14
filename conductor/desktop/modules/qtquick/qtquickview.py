import os
import sys

from Qt import QtGui, QtCore, QtWidgets
from PySide2.QtQuick import QQuickView
import qtmodern.styles
import qtmodern.windows

from conductor.lib import pyside_utils, file_utils, common, exceptions, package_utils
from conductor.desktop.lib import module
# from . import RESOURCES_DIRPATH
RESOURCES_DIRPATH = os.path.join(os.path.dirname(__file__), "resources")


class QtQuickModule(module.DesktopModule):
    _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'qtquick.ui')

    def __init__(self, parent=None):

        super(QtQuickModule, self).__init__(parent=parent)
        uic.loadUi(self._ui_filepath, self)

#         self.ui_qkwgt.engine().quit.connect(QtCore.QCoreApplication.quit)
        self.ui_qkwgt.setSource(QtCore.QUrl("/home/lschlosser/git/conductor_client_desktop/conductor/desktop/modules/qtquick/resources/maroon/maroon.qml"))

        if (self.ui_qkwgt.status() == QQuickView.Error):
            return -1

        self.ui_qkwgt.setResizeMode(QQuickView.SizeRootObjectToView)


#         self.ui_qkwgt.setSource(QtCore.QUrl("/home/lschlosser/git/conductor_client_desktop/conductor/desktop/modules/qtquick/resources/view.qml"))

    def getNavbarVisible(self):
        return True

    def getNavbarName(self):
        return "QtQuick Test"


if __name__ == "__main__":
    from PySide2.QtWidgets import QApplication
    from PySide2.QtQuick import QQuickView
    from PySide2.QtCore import QUrl

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QApplication([])
    view = QQuickView()

    view.setSource(QtCore.QUrl("/home/lschlosser/git/conductor_client_desktop/conductor/desktop/modules/qtquick/resources/maroon/maroon.qml"))

    if (view.status() == QQuickView.Error):
        sys.exit(1)

    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.show()
    app.exec_()
