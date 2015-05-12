import os, sys, uuid, inspect, tempfile
from PySide import QtGui, QtCore, QtUiTools
from conductor.tools import conductor_submit
from conductor import submitter_resources  # This is required so that when the .ui file is loaded, any resources that it uses from the qrc resource file will be found


PACKAGE_DIRPATH = os.path.dirname(__file__)
RESOURCES_DIRPATH = os.path.join(PACKAGE_DIRPATH, "resources")

'''
TODO:
1. Create qt resource package or fix filepaths for all images to be set during code execution
2. about menu? - provide link to studio's conductor url (via yaml config file) 
3. Extendable vs private:  What's the line?


'''

class ConductorSubmitter(QtGui.QMainWindow):
    '''
    Base class for PySide front-end for submitting jobs to Conductor.
    
    Intended to be subclassed for each software context that may need a Conductor 
    front end e.g. for <aya or for Nuke.
    
    The getExtendedWidget method acts as an opportunity for a developer to extend 
    the UI to suit his/her needs. See the getExtendedWidgetthe docstring
      
    '''

    # .ui designer filepath
    _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'submitter.ui')

    _window_title = "Conductor"

    def __init__(self, parent=None):
        super(ConductorSubmitter, self).__init__(parent=parent)
        UiLoader.loadUi(self._ui_filepath, self)
        self.initializeUi()

    def initializeUi(self):
        '''
        Initialize ui properties/behavior
        '''

        # Set the start/end fields to be restricted to integers only
        self.ui_start_frame_lnedt.setValidator(QtGui.QIntValidator())
        self.ui_end_frame_lnedt.setValidator(QtGui.QIntValidator())

        # Set string validation for the custom frame range field
        self._setCustomRangeValidator()
        self.ui_custom_lnedt.textChanged.connect(self._validateCustomFramesText)

        # Set the window title name
        self.setWindowTitle(self._window_title)

        # Set the radio button on for the start/end frames by default
        self.on_ui_start_end_rdbtn_toggled(True)

        # Hide the widget that holds advanced settings. TODO: need to come back to this.
        self.ui_advanced_wgt.hide()

        # Add the extended widget (must be implemented by the child class
        self._addExtendedWidget()

        # shrink UI to be as small as can be
        self.adjustSize()

        # Set the keyboard focus on the frame range radio button
        self.ui_start_end_rdbtn.setFocus()


    def refreshUi(self):
        '''
        Override this method to repopulate the UI with fresh data from the software
        it's running from
        '''
        class_method = "%s.%s" % (self.__class__.__name__, inspect.currentframe().f_code.co_name)
        message = "%s not implemented. Please override method as desribed in its docstring" % class_method
        raise NotImplementedError(message)


    def _addExtendedWidget(self):
        '''
        Add the extended widget to the UI
        '''
        self.extended_widget = self.getExtendedWidget()
        extended_widget_layout = self.ui_extended_container_wgt.layout()
        extended_widget_layout.addWidget(self.extended_widget)


    def getExtendedWidget(self):
        '''
        This method extends the Conductor UI by providing a single PySide widget
        that will be added to the UI. The widget may be any class object derived 
        from QWidget. 
         
        In order to do so, subclass this class and override this method to 
        return the desered widget object.  This widget will be inserted between 
        the Frame Range area and the  Submit button. See illustration below:
        
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

        class_method = "%s.%s" % (self.__class__.__name__, inspect.currentframe().f_code.co_name)
        message = "%s not implemented. Please override method as desribed in its docstring" % class_method
        raise NotImplementedError(message)


    def _setCustomRangeValidator(self):
        '''
        Create a regular expression and set it as a validator on the custom frame
        range field.
        
        The following text entry examples are valid:
            1001
            1001,1004
            1001-1004
            1001-1004x3
            1001, 1004, 
            1001, 1004, 1006-1010x3, 1007, 1008-1010x2
            
        The following text examples are NOT valid:
            1001x3
            1001,1004x3
        '''
        # Establish regex "building blocks" to form full reg ex
        rx_number = "\d+"  # The "number" building block, eg.  acceptes 1001, or 1, or 002
        rx_step = "x\d"  # the "step" building block, e.g. accepts x1000, or x1, or x002
        rx_range_w_step = r"(?:%s-%s(?:%s)?)+" % (rx_number, rx_number, rx_step)  # the "range w option step" building block, e.g 100-100, or 100-100x3, oor
        rx_validation = "((%s|%s), +)+" % (rx_number, rx_range_w_step)  # The final regex which uses a space and comma as a delimeter between multiple frame strings
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


    def setStepFrame(self, step_frame):
        '''
        Set the UI's step frame spinbox value
        '''
        self.ui_step_frame_spnbx.setValue(int(step_frame))

    def getStepFrame(self):
        '''
        Return UI's step frame spinbox value
        '''
        return self.ui_step_frame_spnbx.value()


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


    def generateConductorArgs(self):
        '''
        Return a dictionary which contains the expected conductor arguments and
        their values as key/values
        
        TODO: flesh out the docs for each variable
        available keys:
            cmd: str
            force: bool
            frames: str
            output_path: str
            postcmd: str?
            priority: int?
            resource: ?
            skip_time_check: bool?
            upload_dependent: int? jobid?
            upload_file: str
            upload_only: bool
            upload_paths: list of str?
            usr: str
        '''
        class_method = "%s.%s" % (self.__class__.__name__, inspect.currentframe().f_code.co_name)
        message = "%s not implemented. Please override method as desribed in its docstring" % class_method
        raise NotImplementedError(message)


    def getForceUploadBool(self):
        '''
        Return whether the "Force Upload" checkbox is checked on or off.
        '''
        return self.ui_force_upload_chkbx.isChecked()

    def runConductorSubmission(self, args):
        '''
        Instantiate a Conductor Submit object with the given conductor_args 
        (dict), and execute it. 
        '''


        conductor_args = self.generateConductorArgs()
        for arg_name, arg_value in conductor_args.iteritems():
            print "%s: %s" % (arg_name, arg_value)


#         submission = conductor_submit.Submit(conductor_args)
#         return submission.main()


    @QtCore.Slot(bool, name="on_ui_start_end_rdbtn_toggled")
    def on_ui_start_end_rdbtn_toggled(self, on):

        self.ui_start_end_wgt.setEnabled(on)
        self.ui_custom_wgt.setDisabled(on)


    @QtCore.Slot(name="on_ui_submit_pbtn_clicked")
    def on_ui_submit_pbtn_clicked(self):
        '''
        This gets called when the user pressed the "Submit" button in the UI.
        
        1. Run any presubmission processes.
        2. Run the submission process.
        3. Run any postsubmission processes.
        
        '''
        data = self.runPreSubmission()
        result = self.runConductorSubmission(data)
        return self.runPostSubmission(result)


    def runPreSubmission(self):
        '''
        Run any pre submission processes, returning optional data that can
        be passed into the main runConductorSubmission method
        '''
        return


    def runPostSubmission(self, result):
        '''
        Run any post submission processes, returning optional data that can
        be passed into the main runConductorSubmission method.  The "result" argument
        contains the results of the main runConductorSubmission method.
        '''
        return




    @QtCore.Slot(name="on_ui_refresh_tbtn_clicked")
    def on_ui_refresh_tbtn_clicked(self):
        self.refreshUi()



    def getFrameRangeString(self):
        if self.ui_start_end_rdbtn.isChecked():
            return "%s-%sx%s" % (self.getStartFrame(), self.getEndFrame(), self.getStepFrame())
        else:
            return self.getCustomFrameString()


    def _validateCustomFramesText(self, text):
        '''
        
        '''
        if self.frame_str_validator.validate(text, len(text))[0] == QtGui.QValidator.Invalid:
            style_sheet = "background-color: rgb(130, 63, 63);"
        else:
            style_sheet = ""

        self.ui_custom_lnedt.setStyleSheet(style_sheet)

    def getCoreCount(self):
        '''
        Return the number of cores that the user has selected from the
        "Core Count" combobox
        '''
        return int(self.ui_core_count_cmbx.currentText())


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



def write_dependency_file(dependencies, filepath):
    '''
    Write the given list of depencies to the given filepath
    '''
    with open(filepath, 'w') as file_obj:
        file_obj.write(", ".join(dependencies))
    return filepath


def generate_temporary_filepath():
    '''
    Generate and return a unique filepath name located in the machine's temp 
    directory.
    '''
    temp_dirpath = tempfile.gettempdir()
    filename = "conductor_dependencies_%s" % str(uuid.uuid1())
    return os.path.join(temp_dirpath, filename)




if __name__ == "__main__":
    app = QtGui.QApplication.instance()
    if app is None:
        app = QtGui.QApplication(sys.argv)
    ConductorSubmitter.runUi()
