import os
import sys

from Qt import QtGui, QtCore, QtWidgets
import qtmodern.styles
import qtmodern.windows
from qtpy import uic

from conductor.lib import pyside_utils, file_utils, common, exceptions, package_utils
from conductor.desktop.lib import module
from . import RESOURCES_DIRPATH


class AccountModule(module.DesktopModule):
    _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'account.ui')

    def __init__(self, parent=None):

        super(AccountModule, self).__init__(parent=parent)
        uic.loadUi(self._ui_filepath, self)

    def getNavbarVisible(self):
        return True

    def getNavbarName(self):
        return "Account"


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    qtmodern.styles.dark(app)
    submitter = AccountModule()
    mw = qtmodern.windows.ModernWindow(submitter)
    mw.show()
    sys.exit(app.exec_())
