import os, sys
from PySide import QtGui, QtCore, QtUiTools
# from conductor_client import conductor_submit

PACKAGE_DIRPATH = os.path.dirname(__file__)
RESOURCES_DIRPATH = os.path.join(PACKAGE_DIRPATH, "resources")



class ConductorSubmitter(QtGui.QMainWindow):
    '''
    Base class for PySide front-end for submitting jobs to Conductor.
    
    Intended to be subclassed for each software context that a Conductor front
    end is desired , e.g. subclassed for a PySide UI for Nuke, or a UI for Maya.
    
    The extended_widget_class class attribute acts as an opportunity for a 
    developer to extend the UI to suit his/her needs. See the docstring for the
    "_addExtendedWidget" method.
      
    '''

    # .ui designer filepath
    _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'submitter.ui')

    # conductor icon filepath
    _conductor_icon_filepath = os.path.join(RESOURCES_DIRPATH, "conductor_logo_01_x32.png")
    _conductor_logo_filepath = os.path.join(RESOURCES_DIRPATH, "conductor_logo_red_w_title_x64.png")

    extended_widget_class = None

    def __init__(self, parent=None):
        super(ConductorSubmitter, self).__init__(parent=parent)
        UiLoader.loadUi(self._ui_filepath, self)
        self._initializeUi()

    def _initializeUi(self):
        self.setWindowIcon(QtGui.QIcon(QtGui.QPixmap(self._conductor_icon_filepath)))
        self.ui_logo_lbl.setPixmap(self._conductor_logo_filepath);
        self.ui_start_frame_lnedt.setValidator(QtGui.QIntValidator())
        self.ui_end_frame_lnedt.setValidator(QtGui.QIntValidator())
        self._addExtendedWidget()
        self._setCustomRangeValidator()
        self.ui_custom_lnedt.textChanged.connect(self.validate_custom_text)
        self.on_ui_start_end_rdbtn_toggled(True)


    def _addExtendedWidget(self):
        '''
        Instantiate and embed the widget class (if one is assidnged to the
        extended_widget_class attribute) into the UI. The widget 
        will be inserted (visually) between the frame range section and the 
        submit button. See illustration below
                 ____________________
                |     Conductor      |
                |--------------------|
                |  Frame Range Area  |
                |--------------------|
                |                    |
                |  <EXTENDED WIDGET> |   <-- your extended widget goes here.
                |                    |
                |--------------------|
                |   submit button    |
                |____________________|
         
        '''
        if self.extended_widget_class:
            self.extended_widget = self.extended_widget_class()
            layout = QtGui.QVBoxLayout()
            self.ui_extended_container_wgt.setLayout(layout)
            layout.addWidget(self.extended_widget)

    def _setCustomRangeValidator(self):
        '''
        1001
        1001,1004
        1001-1004
        1001-1004x3
        
        NOT 1001x3
        NOT 1001,1004x3
        '''
        rx_number = "\d+"
        rx_step = "x\d"
        rx_range_w_step = r"(?:%s-%s(?:%s)?)+" % (rx_number, rx_number, rx_step)
        rx_validation = "((%s|%s), +)+" % (rx_number, rx_range_w_step)
        self.frame_str_validator = QtGui.QRegExpValidator(QtCore.QRegExp(rx_validation), None)


    def setFrameRange(self, start, end):
        '''
        Set the UI's start/end frame fields
        '''
        self.setStartFrame(start)
        self.setEndFrame(end)

    def setStartFrame(self, start_frame):
        '''
        Set the UI's start frame field
        '''
        self.ui_start_frame_lnedt.setText(str(start_frame))

    def getStartFrame(self):
        '''
        Return UI's start frame field
        '''
        return str(self.ui_start_frame_lnedt.text())


    def setEndFrame(self, end_frame):
        '''
        Set the UI's end frame field
        '''
        self.ui_end_frame_lnedt.setText(str(end_frame))

    def getEndFrame(self):
        '''
        Return UI's end frame field
        '''
        return str(self.ui_end_frame_lnedt.text())


    def setCustomFrameString(self, custom_frame_str):
        '''
        Set the UI's custom frame field
        '''
        self.ui_custom_lnedt.setText(custom_frame_str)


    def getCustomFrameString(self):
        '''
        Return the UI's custom frame field
        '''
        return str(self.ui_custom_lnedt.text())


    @QtCore.Slot(bool, name="on_ui_start_end_rdbtn_toggled")
    def on_ui_start_end_rdbtn_toggled(self, on):

        self.ui_start_end_wgt.setEnabled(on)
        self.ui_custom_wgt.setDisabled(on)


    @QtCore.Slot(name="on_ui_submit_pbtn_clicked")
    def on_ui_submit_pbtn_clicked(self):
        print "Frame range: %s" % self.getFrameRangeString()



    def getFrameRangeString(self):
        if self.ui_start_end_rdbtn.isChecked():
            return "%s-%s" % (self.getStartFrame(), self.getEndFrame())
        else:
            return self.getCustomFrameString()


    def validate_custom_text(self, text):
        '''
        
        '''
        if self.frame_str_validator.validate(text, len(text))[0] == QtGui.QValidator.Invalid:
            style_sheet = "background-color: rgb(130, 63, 63);"
        else:
            style_sheet = ""

        self.ui_custom_lnedt.setStyleSheet(style_sheet)


    @classmethod
    def runUi(cls):
        '''
        Note that this UI class is to be run directly from a python shell, e.g.
        not within another software's context (such as maya/nuke).
        '''
        app = QtGui.QApplication.instance()
        if app is None:
            app = QtGui.QApplication(sys.argv)
        ui = cls()
        ui.show()
        app.exec_()




class UiLoader(QtUiTools.QUiLoader):
    '''
    #TODO: Re-write docs/comments for this class

    Load a Qt Designer .ui file and returns an instance of the user interface.

    This was taken almost 100% verbatim from a stack overflow example.
    '''

    def __init__(self, baseinstance):
        super(UiLoader, self).__init__(baseinstance)
        self.baseinstance = baseinstance

    def createWidget(self, class_name, parent=None, name=''):
        if parent is None and self.baseinstance:
            # supposed to create the top-level widget, return the base instance
            # instead
            return self.baseinstance
        else:
            # create a new widget for child widgets
            widget = QtUiTools.QUiLoader.createWidget(self, class_name, parent, name)
            if self.baseinstance:
                # set an attribute for the new child widget on the base
                # instance, just like uic.loadUi does.
                setattr(self.baseinstance, name, widget)
            return widget

    @classmethod
    def loadUi(cls, uifile, baseinstance=None):
        '''
        Load a Qt Designer .ui file and returns an instance of the user interface.

        uifile: the file name or file-like object containing the .ui file.
        baseinstance: the optional instance of the Qt base class. If specified then the user interface is created in it. Otherwise a new instance of the base class is automatically created.
        Return type: the QWidget sub-class that implements the user interface.
        '''
        loader = cls(baseinstance)
        widget = loader.load(uifile)
        QtCore.QMetaObject.connectSlotsByName(widget)
        return widget



if __name__ == "__main__":
    app = QtGui.QApplication.instance()
    if app is None:
        app = QtGui.QApplication(sys.argv)
    ConductorSubmitter.runUi()
