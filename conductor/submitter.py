import os
import sys
import inspect
import traceback
from PySide import QtGui, QtCore
import imp
import re

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import conductor
import conductor.setup
from conductor.lib import  conductor_submit, pyside_utils
from conductor import submitter_resources  # This is a required import  so that when the .ui file is loaded, any resources that it uses from the qrc resource file will be found

PACKAGE_DIRPATH = os.path.dirname(__file__)
RESOURCES_DIRPATH = os.path.join(PACKAGE_DIRPATH, "resources")
logger = conductor.setup.logger
DEFAULT_ATTRS = ["ui_notify_lnedt", "ui_start_frame_lnedt", "ui_end_frame_lnedt",
                 "ui_custom_lnedt", "ui_instance_type_cmbx", "ui_resource_lnedt",
                 "ui_output_path_lnedt"]
LAST_ATTRS = ["ui_notify_lnedt", "ui_instance_type_cmbx", "ui_resource_lnedt"]

'''
TODO:
1. Create qt resource package or fix filepaths for all images to be set during code execution
2. about menu? - provide link to studio's conductor url (via yaml config file) 
4. rename files to "maya.py" and "nuke.py" ??
5. consider conforming all code to camel case (including .ui widgets). 
6. Consider adding validation to the base class so that inheritance can be used.
7. tool tips!  - ask greg about a tool tip for "resource"
8. What about the advanced options? ("Force Upload" and "Dependency Job" )
9. what are the available commands for the "cmd" arg?  These should be documented:
    nuke-render  (what flags are available?)
    maya2015Render  (what flags are available?)
10: validate resource string only [a-z0-9-]
11: Conductor instance types should be queried from config file (or the web?)
'''

class ConductorSubmitter(QtGui.QMainWindow):
    '''
    Base class for PySide front-end for submitting jobs to Conductor.
    
    Intended to be subclassed for each software context that may need a Conductor 
    front end e.g. for Maya or Nuke.
    
    The self.getExtendedWidget method acts as an opportunity for a developer to extend 
    the UI to suit his/her needs. See the getExtendedWidgetthe docstring
      
        '''

    # .ui designer filepath
    _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'submitter.ui')

    # The text in the title bar of the UI
    _window_title = "Conductor"

    # The instance type that is set by default in the UI. This integer
    # corresponds to the core count of the conductor instance type
    default_instance_type = 16

    link_color = "rgb(200,100,100)"

    def __init__(self, parent=None):
        super(ConductorSubmitter, self).__init__(parent=parent)
        pyside_utils.UiLoader.loadUi(self._ui_filepath, self)
        self.initializeUi()

    def initializeUi(self):
        '''
        Initialize ui properties/behavior
        '''
        self.defaults = self.getDefaults()

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

        # Populate the Instance Type combobox with the available instance configs
        self.populateInstanceTypeCmbx()

        # Set the default instance type
        self.setInstanceType(self.default_instance_type)

        # Hide the widget that holds advanced settings. TODO: need to come back to this.
        self.ui_advanced_wgt.hide()

        # Add the extended widget (must be implemented by the child class
        self._addExtendedWidget()

        # shrink UI to be as small as can be
        self.adjustSize()

        # Set the keyboard focus on the frame range radio button
        self.ui_start_end_rdbtn.setFocus()

        self.ui_choose_path_btn.clicked.connect(self.browseOutput)


    def browseOutput(self):
        directory = str(QtGui.QFileDialog.getExistingDirectory(self, "Select Directory"))
        if not directory:
            return
        directory = re.sub("\\\\", "/", directory)
        self.ui_output_path_lnedt.setText(directory)


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

    def populateInstanceTypeCmbx(self):
        '''
        Populate the 
        '''
        instance_types = get_conductor_instance_types()
        self.ui_instance_type_cmbx.clear()
        for instance_info in instance_types:
            self.ui_instance_type_cmbx.addItem(instance_info['description'], userData=instance_info)

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


    def setInstanceType(self, core_count):
        '''
        Set the UI's "Instance Type" combobox.  This is done by specifying the
        core count int.
        '''

        item_idx = self.ui_instance_type_cmbx.findData({"cores": core_count, "flavor": "standard", "description": "16 core, 60.0GB Mem"})
        if item_idx == -1:
            raise Exception("Could not find combobox entry for core count: %s!"
                            "This should never happen!" % core_count)
        return self.ui_instance_type_cmbx.setCurrentIndex(item_idx)

    def getInstanceType(self):
        '''
        Return the number of cores that the user has selected from the
        "Instance Type" combobox
        '''
        return self.ui_instance_type_cmbx.itemData(self.ui_instance_type_cmbx.currentIndex())

    def setResource(self, resource_str):
        '''
        Set the UI's Resource field
        '''
        self.ui_resource_lnedt.setText(resource_str)


    def getResource(self):
        '''
        Return the UI's Resurce field
        '''
        return str(self.ui_resource_lnedt.text())

    def generateConductorArgs(self, args):
        '''
        Return a dictionary which contains the necessary conductor argument names
        and their values.  This dictionary will ultimately be passed directly 
        into a conductor Submit object when instantiating/calling it.
        
        Generally, the majority of the values that one would populate this dictionary
        with would be found by quering this UI, e.g.from the "frames" section.
         

        example:  TODO: Give a real example
           {'cmd': str,
            'cores': int,
            'force': bool,
            'frames': str,
            'output_path': str,
            'postcmd': str?,
            'priority': int?,
            'resource': ?,
            'upload_file': str,
            'upload_only': bool,
            'upload_paths': list of str?,
            'user': str}
            
        
        TODO: flesh out the docs for each variable
        available keys:
            cmd: str
            cores: int
            force: bool
            frames: str
            output_path: str
            postcmd: str?
            priority: int?
            resource: ?
            upload_file: str
            upload_only: bool
            upload_paths: list of str?
            user: str

        '''
        class_method = "%s.%s" % (self.__class__.__name__, inspect.currentframe().f_code.co_name)
        message = "%s not implemented. Please override method as desribed in its docstring" % class_method
        raise NotImplementedError(message)


    def getDockerImage(self):
        '''
        Return the Docker image name (str) to use on Conductor.
        Example: "Maya2015"
        By default, this will return the docker image that is listed in the 
        conductor config.yml file (or None if one does not exist).
        Child classes should override this method to return the image that 
        is appropriate for the software context (e.g nuke or maya, etc)
        '''
        return conductor.setup.CONFIG.get("docker_image")


    def getForceUploadBool(self):
        '''
        Return whether the "Force Upload" checkbox is checked on or off.
        '''
        return self.ui_force_upload_chkbx.isChecked()

    @pyside_utils.wait_cursor
    @pyside_utils.wait_message("Conductor", "Submitting Conductor Job...")
    def runConductorSubmission(self, data):
        '''
        Instantiate a Conductor Submit object with the given conductor_args 
        (dict), and execute it. 
        '''
        # Generate a dictionary of arguments to feed conductor
        conductor_args = self.generateConductorArgs(data)

        # Print out the values for each argument
        logger.debug("runConductorSubmission ARGS:")
        for arg_name, arg_value in conductor_args.iteritems():
            logger.debug("%s: %s", arg_name, arg_value)

        # Instantiate a conductor Submit object and run the submission!
        try:
            submission = conductor_submit.Submit(conductor_args)
            response, response_code = submission.main()

        except:
            title = "Job submission failure"
            message = "".join(traceback.format_exception(*sys.exc_info()))
            pyside_utils.launch_error_box(title, message, self)
            raise

        return response_code, response


    def launch_result_dialog(self, response_code, response):

        # If the job submitted successfully
        if response_code in [201, 204]:
            job_id = str(response.get("jobid") or 0).zfill(5)
            title = "Job Submitted"
            job_url = conductor.setup.CONFIG['url'] + "/job/" + job_id
            message = ('<html><head/><body><p>Job submitted: '
                       '<a href="%s"><span style=" text-decoration: underline; '
                       'color:%s;">%s</span></a></p></body></html>') % (job_url, self.link_color, job_id)
            pyside_utils.launch_message_box(title, message, is_richtext=True, parent=self)
        # All other response codes indicate a submission failure.
        else:
            title = "Job Submission Failure"
            message = "Job submission failed: error %s" % response_code
            pyside_utils.launch_error_box(title, message, parent=self)


    @QtCore.Slot(bool, name="on_ui_start_end_rdbtn_toggled")
    def on_ui_start_end_rdbtn_toggled(self, on):

        self.ui_start_end_wgt.setEnabled(on)
        self.ui_custom_wgt.setDisabled(on)


    @QtCore.Slot(name="on_ui_submit_pbtn_clicked")
    def on_ui_submit_pbtn_clicked(self):
        '''
        This gets called when the user pressed the "Submit" button in the UI.
        
      
        -- Submission Control Flow ---
        Below is the method calling order of when a user presses the "submit" 
        button in the UI: 
            1. self.runPreSubmission()         # Run any pre-submission processes.
            2. self.runConductorSubmission()   # Run the submission process.
            3. self.runPostSubmission()        # Run any post-submission processes.
            
        Each one of these methods has the opportunity to return data, which in turn
        will be available to the next method that is called.  If that mechanism
        does not meet all pre/post submission needs, then overriding those methods
        is also an available/appropriate methodology.  
        
        '''

        data = self.runPreSubmission()
        response_code, response = self.runConductorSubmission(data)
        self.runPostSubmission(response_code)

        self.launch_result_dialog(response_code, response)


    def runPreSubmission(self):
        '''
        Run any pre submission processes, returning optional data that can
        be passed into the main runConductorSubmission method
        '''
        return


    def runPostSubmission(self, data):
        '''
        Run any post submission processes.  The "data" argument contains the results 
        of the main runConductorSubmission method, so that any results can
        be "inspected" and acted upon if desired.
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





def get_conductor_instance_types():
    '''
    Return a dictionary which represents the different Conductor instance
    types available.  They key is the "core count" (which gets fed into
    Conductor's Submit object as an argument), and the value is the string that
    will appear in the ui to describe the instance type.
    
    TODO: This information should probably be put into and read from an external
          file (yaml, json, etc) 
    '''
    instances = [{"cores": 2, "flavor": "highcpu", "description": " 2 core 1.8GB Mem"},
                 {"cores": 2, "flavor": "standard", "description": " 2 core,  7.5GB Mem"},
                 {"cores": 2, "flavor": "highmem", "description": " 2 core, 13.0GB Mem"},
                 {"cores": 4, "flavor": "highcpu", "description": " 4 core, 3.6GB Mem"},
                 {"cores": 4, "flavor": "standard", "description": " 4 core, 15.0GB Mem"},
                 {"cores": 4, "flavor": "highmem", "description": " 4 core, 26.0GB Mem"},
                 {"cores": 8, "flavor": "highcpu", "description": " 8 core, 7.20GB Mem"},
                 {"cores": 8, "flavor": "standard", "description": " 8 core, 30.0GB Mem"},
                 {"cores": 8, "flavor": "highmem", "description": " 8 core, 52.0GB Mem"},
                 {"cores": 16, "flavor": "highcpu", "description": "16 core, 14.4GB Mem"},
                 {"cores": 16, "flavor": "standard", "description": "16 core, 60.0GB Mem"},
                 {"cores": 16, "flavor": "highmem", "description": "16 core, 104GB Mem"},
                 {"cores": 32, "flavor": "highcpu", "description": "32 core, 28.8GB Mem"},
                 {"cores": 32, "flavor": "standard", "description": "32 core, 120GB Mem"},
                 {"cores": 32, "flavor": "highmem", "description": "32 core, 208GB Mem"}]
    return instances



if __name__ == "__main__":
    app = QtGui.QApplication.instance()
    if app is None:
        app = QtGui.QApplication(sys.argv)
    ConductorSubmitter.runUi()
