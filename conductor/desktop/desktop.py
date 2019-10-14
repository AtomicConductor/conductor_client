import collections
import functools
import imp
import inspect
from itertools import groupby
import logging
import os
import operator
from pprint import pformat
import random
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
from qtpy import uic
from PySide2 import QtCore, QtWidgets
import PySide2.QtCore
import PySide2.QtWidgets
import PySide2.QtUiTools
import PySide2.QtXml
import PySide2.QtWebEngineWidgets
import qtmodern.styles
import qtmodern.windows
import PySide2.QtPrintSupport

import conductor
from conductor import submitter
from conductor.lib import pyside_utils
from conductor.desktop import modules

# This is a required import  so that when the .ui file is loaded, any
# resources that it uses from the qrc resource file will be found
from conductor import submitter_resources

SUCCESS_CODES_SUBMIT = [201, 204]
TASK_CONFIRMATION_THRESHOLD = 1000

from conductor.desktop.modules.account.account import AccountModule
from conductor.desktop.modules.home.home import HomeModule
from conductor.desktop.modules.downloader.downloader import DownloaderModule
from conductor.desktop.modules.submission.submission import SubmissionModule
from conductor.desktop.modules.web.web import WebModule
from conductor.desktop.modules.qtquick.qtquickwidget import QtQuickModule


RESOURCES_DIRPATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")

# PACKAGE_DIRPATH = os.path.dirname(__file__)
# RESOURCES_DIRPATH = os.path.join(PACKAGE_DIRPATH, "resources")

MODULES = (
    HomeModule,
    AccountModule,
    DownloaderModule,
    WebModule,
    QtQuickModule,
    #     SubmissionModule,
)


logger = logging.getLogger(__name__)


# COMMAND_TEMPLATES = (
#     {
#         "product": "maya"
#         "command":
#         }
#
#
#     )
#
#         cmd_template = (
#             'modo_cl -dboff:crashreport -cmd:@{render_script_filepath}'
#             '"'
#             ' --modo-filepath {modo_filepath}'
#             ' --output-path {output_path}'
#             ' --frame-start {frame_start}'
#             ' --frame-end {frame_end}'
#             ' --frame-step {frame_step}'
#             '{project_dir}'
#             '{res_x}'
#             '{res_y}'
#             '{file_format}'
#             '{output_pattern}'
#             '{render_pass_group}'
#             '"'
#         )


class Signals(QtCore.QObject):
    pass


class Slots(QtCore.QObject):
    pass


class ConductorDesktop(QtWidgets.QMainWindow):
    """Base class for PySide front-end for submitting jobs to Conductor.

    Intended to be subclassed for each software context that may need a Conductor
    front end e.g. for Maya or Nuke.

    The self.getExtendedWidget method acts as an opportunity for a developer to extend
    the UI to suit his/her needs. See the getExtendedWidgetthe docstring
    """

    # .ui designer filepath
    _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'desktop.ui')

    # company name
    company_name = "Conductor"

    # The text in the title bar of the UI
    _window_title = company_name

    def __init__(self, parent=None):

        super(ConductorDesktop, self).__init__(parent=parent)
        uic.loadUi(self._ui_filepath, self)
        pyside_utils.apply_style_file(self, os.path.join(RESOURCES_DIRPATH, "style.qss"), append=True)

        self._modules = self.loadModules()
        self.initialize_ui()

    def initialize_ui(self):
        '''
        '''
#         self.ui_navbar_trwgt.itemSelectionChanged.connect(self.itemSelectionChangedHandler)
        self.ui_navbar_trwgt.currentItemChanged.connect(self.currentItemChangedHandler)

    def loadModules(self):
        modulz = []
        for ModuleClass in MODULES:
            modulz.append(self.loadModule(ModuleClass))

    def itemSelectionChangedHandler(self):
        selected_item = self.ui_navbar_trwgt.currentItem()
        self.focusModule(selected_item._module)

    def currentItemChangedHandler(self, clicked_item, prior_item):
        if clicked_item:
            clicked_item._module.show()
        if prior_item:
            prior_item._module.hide()

    def handler(self, *args, **kwargs):
        print ("args", args)
        print ("kwargs", kwargs)

    def loadModule(self, ModuleClass):
        '''
        Module

        - instantiate widget
        - add to navbar
        menu name
        menu index
        '''
        module = ModuleClass()
        self.ui_module_wgt.layout().addWidget(module)
        module.hide()
        if module.getNavbarVisible():
            print("adding to navbar")
            self.addNavbarModule(module)

#     def focusModule(self, module):
#         print ("module", module)
#         module.show()

    def addNavbarModule(self, module):
        navbar_item = self.createNavbarTreeWidgetItem(module)
        navbar_item._module = module
        self.ui_navbar_trwgt.addTopLevelItem(navbar_item)

    @staticmethod
    def createNavbarTreeWidgetItem(module):
        tree_item = QtWidgets.QTreeWidgetItem([module.getNavbarName()])
        tree_item.module = module
        return tree_item


#     def getLoadedModules(self):


def set_random_locale():

    # language, country
    locales = (
        (QtCore.QLocale.Language.English, QtCore.QLocale.Country.UnitedStates),
        (QtCore.QLocale.Language.English, QtCore.QLocale.Country.Canada),
        (QtCore.QLocale.Language.English, QtCore.QLocale.Country.UnitedKingdom),
        (QtCore.QLocale.Language.English, QtCore.QLocale.Country.Australia),
        (QtCore.QLocale.Language.Spanish, QtCore.QLocale.Country.Spain),
        (QtCore.QLocale.Language.Spanish, QtCore.QLocale.Country.Mexico),
        (QtCore.QLocale.Language.Spanish, QtCore.QLocale.Country.Brazil),
        (QtCore.QLocale.Language.Spanish, QtCore.QLocale.Country.Argentina),
        (QtCore.QLocale.Language.French, QtCore.QLocale.Country.France),
        (QtCore.QLocale.Language.French, QtCore.QLocale.Country.Canada),
        (QtCore.QLocale.Language.SwissGerman, QtCore.QLocale.Country.Switzerland),
        (QtCore.QLocale.Language.Swedish, QtCore.QLocale.Country.Sweden),
        (QtCore.QLocale.Language.Danish, QtCore.QLocale.Country.Denmark),
    )

    locale = QtCore.QLocale(*random.choice(locales))

    QtCore.QLocale.setDefault(locale)
    print ("Using Locale Language {}, Country {}".format(locale.language(), locale.country()))


if __name__ == "__main__":
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseStyleSheetPropagationInWidgetStyles)
    set_random_locale()
#     print ("Screen count", QtCore.QCoreApplication.desktop().screenCount())
    print ("paths", QtCore.QCoreApplication.libraryPaths())
    app = QtWidgets.QApplication(sys.argv)
    print ("screens", app.screens())
    submitter = ConductorDesktop()

    ### DEFAULT STYLING ###
#     submitter.show()

    ### QTMODERN STYLING ###
    qtmodern.styles.dark(app)
    mw = qtmodern.windows.ModernWindow(submitter)
    mw.show()
    mw.windowHandle().setScreen(app.screens()[0])

    sys.exit(app.exec_())


#
# import sys
# import random
# from PySide2.QtWidgets import (QApplication, QLabel, QPushButton,
#                                QVBoxLayout, QWidget)
# from PySide2.QtCore import Slot, Qt, QCoreApplication
#
#
# class MyWidget(QWidget):
#     def __init__(self):
#         QWidget.__init__(self)
#
#         self.hello = ["Hallo Welt", "Hei maailma",
#                       "Hola Mundo"]
#
#         self.button = QPushButton("Click me!")
#         self.text = QLabel("Hello World")
#         self.text.setAlignment(Qt.AlignCenter)
#
#         self.layout = QVBoxLayout()
#         self.layout.addWidget(self.text)
#         self.layout.addWidget(self.button)
#         self.setLayout(self.layout)
#
#         # Connecting the signal
#         self.button.clicked.connect(self.magic)
#
#     @Slot()
#     def magic(self):
#         self.text.setText(random.choice(self.hello))


# if __name__ == "__main__":
#     app_context = ApplicationContext()
#     print ("paths",  PySide2.QtCore.QCoreApplication.libraryPaths())
# #     app = QApplication(sys.argv)
#
#     widget = MyWidget()
#     widget.resize(800, 600)
#     widget.show()
#     sys.exit(app_context.app.exec_())
