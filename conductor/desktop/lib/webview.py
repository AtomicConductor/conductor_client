import collections
import functools
import imp
import inspect
from itertools import groupby
import logging
import os
import operator
from pprint import pformat
import sys
import traceback


from fbs_runtime.application_context.PySide2 import ApplicationContext

# from Qt import QtCore, QtWidgets
# import Qt
import shiboken2
import shiboken2.shiboken2

try:
    shiboken2.shiboken2.ownedByPython("dog")
except:
    pass
shiboken2.shiboken2.VoidPtr(b"asdasd")
import PySide2

from PySide2 import QtCore, QtWidgets
import PySide2.QtCore
import PySide2.QtWidgets
import PySide2.QtUiTools
import PySide2.QtXml

import qtmodern.styles
import qtmodern.windows

import PySide2.QtWebEngineWidgets

import conductor
from conductor import submitter
from conductor.lib import pyside_utils
from conductor.desktop import modules

# This is a required import  so that when the .ui file is loaded, any
# resources that it uses from the qrc resource file will be found
from conductor import submitter_resources

PACKAGE_DIRPATH = conductor.__path__[0]
RESOURCES_DIRPATH = os.path.join(PACKAGE_DIRPATH, "resources")
SUCCESS_CODES_SUBMIT = [201, 204]
TASK_CONFIRMATION_THRESHOLD = 1000

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    widget = PySide2.QtWebEngineWidgets.QWebEngineView()
    widget.load(PySide2.QtCore.QUrl("https://www.conductortech.com"))
    widget.show()
    sys.exit(app.exec_())
