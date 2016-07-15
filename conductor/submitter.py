import logging
import os
import operator
import sys
import inspect
import functools
import traceback
from PySide import QtGui, QtCore
import imp

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conductor import CONFIG

from conductor.lib import  conductor_submit, pyside_utils, common, loggeria, api_client
from conductor import submitter_resources  # This is a required import  so that when the .ui file is loaded, any resources that it uses from the qrc resource file will be found

PACKAGE_DIRPATH = os.path.dirname(__file__)
RESOURCES_DIRPATH = os.path.join(PACKAGE_DIRPATH, "resources")
SUCCESS_CODES_SUBMIT = [201, 204]

logger = logging.getLogger(__name__)



'''
TODO:
1. Create qt resource package or fix filepaths for all images to be set during code execution
2. about menu? - provide link to studio's conductor url (via yaml config file) 
5. consider conforming all code to camel case (including .ui widgets). 
6. Consider adding validation to the base class so that inheritance can be used.
7. tool tips for all widget fields
8. What about the advanced options? ("Force Upload" and "Dependency Job" )
9. what are the available commands for the "cmd" arg?

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

    # company name
    company_name = "Conductor"

    # The text in the title bar of the UI
    _window_title = company_name

    # The instance type that is set by default in the UI. This integer
    # corresponds to the core count of the conductor instance type
    default_instance_type = 16

    link_color = "rgb(200,100,100)"

    def __init__(self, parent=None):
        '''
        1. Load the ui file
        2. Initialize widgets (set behavior, populate options, resize/reformat)
        3. Load any user settings to restore widget values from user preferences 
        '''
        super(ConductorSubmitter, self).__init__(parent=parent)
        pyside_utils.UiLoader.loadUi(self._ui_filepath, self)
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

        # connect the scout job checkbox signal
        self.ui_scout_job_chkbx.stateChanged.connect(self.saveScoutJobPref)

        # Set the window title name
        self.setWindowTitle(self._window_title)

        # Setup the top menu bar
        self.setupMenuBar()

        # Set the radio button on for the start/end frames by default
        self.on_ui_start_end_rdbtn_toggled(True)

        # Populate the Instance Type combobox with the available instance configs
        self.populateInstanceTypeCmbx()

        # Set the default instance type
        self.setInstanceType(self.default_instance_type)

        # Populate the Project combobox with customer's projects
        self.populateProjectCmbx()

        # Set the default project by querying the config
        default_project = CONFIG.get('project')
        if default_project:
            self.setProject(default_project, strict=False)

        # Instantiate a user prefs  object
        self.prefs = SubmitterPrefs(company_name=self.company_name,
                                    application_name=self.__class__.__name__,
                                    file_widgets=self.getUserPrefsFileWidgets(),
                                    global_widgets=self.getUserPrefsGlobalWidgets())


        # Apply the user settings for scout job use
        self.LoadScoutJobCheckboxPreference()

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


    def setupMenuBar(self):
        '''
        Setup the gui's menu bar (The top menu bar)
        '''
        menubar = self.menuBar
        assert menubar, "No menubar found!"

        # Add the Logging Menu
        self.addLoggingMenu(self.ui_set_log_level_menu)

        # Connect the "reset preferences" action
        self.addResetPreferencesMenu(self.ui_reset_preferences_menu)

    def addLoggingMenu(self, menu):
        '''
        For the given menu object, dynamically generate a action item for
        each log level (from the loggeria module). 
        '''
        conductor_logger = loggeria.get_conductor_logger()
        current_level = conductor_logger.level

        # Create an action group (this allows for mutually exclusive checkboxes (radio buttons)
        action_group = QtGui.QActionGroup(menu)

        # loop by order of log_level value
        for level_name, level_value in sorted(loggeria.LEVEL_MAP.iteritems(),
                                              key=operator.itemgetter(1), reverse=True):
            # Generate the function that the menu action will call
            func = functools.partial(loggeria.set_conductor_log_level, log_level=level_name)
            action = menu.addAction(level_name, func)
            action.setCheckable(True)
            # Set the action item to be checked if its log level matches the current log level
            action.setChecked(current_level == level_value)
            action_group.addAction(action);



    def addResetPreferencesMenu(self, menu):
        '''
        For the given menu object, dynamically generate a action item for
        each log level (from the loggeria module). 
        '''

        # RESET ALL PREFERENCES
        action_name = "Gloal Preferences"
        title = "Reset Global Preferences"
        message = "Reset Global Conductor preferences"
        global_func = functools.partial(self._resetPreferences, title, message)
        global_action = menu.addAction(action_name, global_func)
        global_action.setToolTip(message)


        # RESET FILE PREFERENCES
        action_name = "File Preferences"
        title = "Reset file Preferencess"
        message = "Reset the Conductor preferences for the open file?"
        source_filepath = self.getSourceFilepath()
        fle_func = functools.partial(self._resetPreferences, title, message, filepath=source_filepath)
        file_action = menu.addAction(action_name, fle_func)
        file_action.setToolTip(message)


    def _resetPreferences(self, title, message, filepath=None):
        '''
        Prompt the user to delete their preferences, and delete them if yes.
        
        If a filepath is given, then delete the preferenes for the given filepath.
        Otherwise delete the global preferences.
        '''
        # Prompt the user
        yes, _ = pyside_utils.launch_yes_no_dialog(title, message,
                                                   show_not_agin_checkbox=False,
                                                   parent=self)
        # If the user has confirmed deletion
        if yes:
            if filepath:
                self.prefs.clearFilePrefs(filepath)
            else:
                self.prefs.clearGlobalPrefs()

            self.prefs.sync()
            # show confirmation of deletion
            pyside_utils.launch_message_box("Deleted",
                                            "Preferences Deleted",
                                            parent=self)


    def populateInstanceTypeCmbx(self):
        '''
        Populate the Instance combobox with all of the available instance types
        '''
        instance_types = common.get_conductor_instance_types()
        self.ui_instance_type_cmbx.clear()
        for instance_info in instance_types:
            self.ui_instance_type_cmbx.addItem(instance_info['description'], userData=instance_info)

    def populateProjectCmbx(self):
        '''
        Populate the project combobox with project names.  If any projects are
        specified in the config file, then use them. Otherwise query Conductor
        for all projects
        '''
        self.ui_project_cmbx.clear()
        for project in CONFIG.get("projects") or api_client.request_projects():
            self.ui_project_cmbx.addItem(project)

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

    def setProject(self, project_str, strict=True):
        '''
        Set the UI's Project field
        '''
        index = self.ui_project_cmbx.findText(project_str)
        if index == -1:
            msg = "Project combobox entry does not exist: %s" % project_str
            logger.warning(msg)
            if strict:
                raise Exception()

        self.ui_project_cmbx.setCurrentIndex(index)

    def getProject(self):
        '''
        Return the UI's Projectj  field
        '''
        return str(self.ui_project_cmbx.currentText())


    def setOutputDir(self, dirpath):
        '''
        Set the UI's Output Directory field
        '''
        self.ui_output_directory_lnedt.setText(dirpath)


    def getOutputDir(self):
        '''
        Return the UI's Output Directory field
        '''
        return str(self.ui_output_directory_lnedt.text()).replace("\\", "/")


    def getNotifications(self):
        '''
        Return the UI's Notificaiton field
        '''
        return str(self.ui_notify_lnedt.text())

    def setNotifications(self, value):
        '''
        Set the UI's Notification field to the given value
        '''
        self.ui_notify_lnedt.setText(str(value))


    def getScoutJobCheckbox(self):
        '''
        Return the checkbox value for the "Scout Job" checkbox 
        '''
        return self.ui_scout_job_chkbx.isChecked()

    def setScoutJobCheckbox(self, bool_):
        '''
        Set the checkbox value for the "Scout Job" checkbox 
        '''
        return self.ui_scout_job_chkbx.setChecked(bool_)

    def generateConductorArgs(self, data):
        '''
        Return a dictionary which contains the necessary conductor argument names
        and their values.  This dictionary will ultimately be passed directly 
        into a conductor Submit object when instantiating/calling it.
        
        Generally, the majority of the values that one would populate this dictionary
        with would be found by quering this UI, e.g.from the "frames" section of ui.
           
        '''
        conductor_args = {}

        conductor_args["cores"] = self.getInstanceType()['cores']
        conductor_args["environment"] = self.getEnvironment()
        conductor_args["force"] = self.getForceUploadBool()
        conductor_args["frames"] = self.getFrameRangeString()
        conductor_args["job_title"] = self.getJobTitle()
        conductor_args["local_upload"] = self.getLocalUpload()
        conductor_args["machine_type"] = self.getInstanceType()['flavor']
        conductor_args["notify"] = self.getNotifications()
        conductor_args["output_path"] = self.getOutputDir()
        conductor_args["project"] = self.getProject()
        conductor_args["scout_frames"] = self.getScoutFrames()
        return conductor_args

    def getCommand(self):
        '''
        Return the command string that Conductor will execute
        '''
        class_method = "%s.%s" % (self.__class__.__name__, inspect.currentframe().f_code.co_name)
        message = "%s not implemented. Please override method as desribed in its docstring" % class_method
        raise NotImplementedError(message)


    def getEnvironment(self):
        '''
        Return a dictionary of environment variables to use for the Job's
        environment
        '''
        #  Get any environment variable settings from config.yml
        environment = CONFIG.get("environment") or {}
        assert isinstance(environment, dict), "Not a dictionary: %s" % environment
        return environment

    def getForceUploadBool(self):
        '''
        Return whether the "Force Upload" checkbox is checked on or off.
        '''
        return self.ui_force_upload_chkbx.isChecked()

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

        return self._runSubmission(conductor_args)



    @pyside_utils.wait_cursor
    @pyside_utils.wait_message("Conductor", "Submitting Conductor Job...")
    def _runSubmission(self, conductor_args):
        try:
            submission = conductor_submit.Submit(conductor_args)
            response, response_code = submission.main()

        except:
            title = "Job submission failure"
            message = "".join(traceback.format_exception(*sys.exc_info()))
            pyside_utils.launch_error_box(title, message, self)
            raise
        return response_code, response

    def getLocalUpload(self):
        '''
        Return a bool indicating whether the uploading process should occur on
        this machine or whether it should get offloaded to the uploader daemon.
        If False, uploading will occur on the daemon.
        
        Simply return the value set in the config.yml.  In the future this option
        may be exposed in the UI
        '''
        return CONFIG.get("local_upload")


    def launch_result_dialog(self, response_code, response):

        # If the job submitted successfully
        if response_code in SUCCESS_CODES_SUBMIT:
            job_id = str(response.get("jobid") or 0).zfill(5)
            title = "Job Submitted"
            job_url = CONFIG['url'] + "/job/" + job_id
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

        # Launch a dialog box what diesplays the results of the job submission
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


    @QtCore.Slot(name="on_ui_choose_output_path_pbtn_clicked")
    def on_ui_choose_output_path_pbtn_clicked(self):

        dirpath = str(QtGui.QFileDialog.getExistingDirectory(self, "Select Directory"))
        if dirpath:
            self.setOutputDir(dirpath)

    def getFrameRangeString(self):
        if self.ui_start_end_rdbtn.isChecked():
            return "%s-%sx%s" % (self.getStartFrame(), self.getEndFrame(), self.getStepFrame())
        else:
            return self.getCustomFrameString()


    def _validateCustomFramesText(self, text):
        '''
        Validate that the given text conforms to a valid frame range expression
        If the text does not conform to the validator, colorize the lineedit so
        that it's apparent to the user.
        '''
        if not text or self.frame_str_validator.validate(text, len(text))[0] == QtGui.QValidator.Invalid:
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


    def getUserPrefsGlobalWidgets(self):
        '''
        Return a list of widget objects that are appropriate for restoring their
        state (values) from a user's preference file. Specifically, these widgets 
        are those which a user's GLOBAL  preferences should be recorded/loaded for. 
        These widgets are identified by a dynamic property that has been set on 
        them via Qt Designer.
        
        '''
        pref_identifier = "isGlobalUserPref"
        return pyside_utils.get_widgets_by_property(self,
                                                    pref_identifier,
                                                    match_value=True,
                                                    property_value=True)
    def getUserPrefsFileWidgets(self):
        '''
        Return a list of widget objects that are appropriate for restoring their
        state (values) from a user's preference file. Specifically, these widgets 
        are those which a user's FILE-SPECIFIC should be recorded/loaded for. 
        These widgets are identified by a dynamic property that has been set on 
        them via Qt Designer.
        '''
        pref_identifier = "isFileUserPref"
        return pyside_utils.get_widgets_by_property(self,
                                                    pref_identifier,
                                                    match_value=True,
                                                    property_value=True)


    def getSourceFilepath(self):
        '''
        Return the filepath for the currently open file. This is  the currently
        opened maya/katana/nuke file, etc
        '''

        class_method = "%s.%s" % (self.__class__.__name__, inspect.currentframe().f_code.co_name)
        message = "%s not implemented. Please override method as desribed in its docstring" % class_method
        raise NotImplementedError(message)


    def loadUserSettings(self):
        '''
        Read and apply user preferences (widget values, etc)
        '''
        try:
            self.prefs.sync()
            source_filepath = self.getSourceFilepath()
            self.prefs.loadSubmitterUserPrefs(source_filepath)
        except:
            settings_filepath = self.prefs.getSettingsFilepath()
            message = ("Unable to apply user settings. "
                       "You may want to modify/delete settings here: %s" % settings_filepath)
            logger.exception(message)

    def saveUserSettings(self):
        '''
        Save current widget settings to the user's preference file.  These settings
        are recorded per source file (maya/katana/nuke file, etc).
        '''
        try:
            source_filepath = self.getSourceFilepath()
            self.prefs.saveSubmitterUserPrefs(source_filepath)
            self.prefs.sync()
        except:
            logger.exception("Unable to save user settings:")

    def closeEvent(self, event):
        '''
        When the Conductor UI is closed, save the user settings.
        '''
        self.saveUserSettings()
        super(ConductorSubmitter, self).closeEvent(event)

    def getEnforcedMd5s(self):
        '''
        Note that this is only relevant when local_upload=False.
        
        Return a dictionary of any filepaths and their corresponding md5 hashes
        that should be verified before uploading to cloud storage.  
        
        When local_upload is False, uploading files to cloud storage is handled
        by an uploader daemon. Because there can be a time delay between when
        a user has pressed "submit" and when the daemon actually goes to upload
        the files to cloud storage, there is the possibility that files have
        actually changes on disk.  For example, a user may submit 3 jobs to
        conductor within 7 seconds of one another, by quickly rotating the camera, 
        saving the maya scene on top of itself, and pressing "Submit" (and doing
        this three time).  Though this is probably not a great workflow, 
        it's something that needs to be guarded against.
        
        This method returns a dictionary of filepaths and and their corresponding 
        md5 hashes, which is used by the uploader daemon when uploading the files
        to conductor. The daemon will do its own md5 hash of all files in 
        this dictionary,and match it against the md5s that the dictionary provides.
        If the uploader finds a mismatch then it fails the upload process (and
        fails the job).
        
        Generally there is gray area as to what is considered "acceptable" for
        files being changed from underneath the feet of the artist.  Because a source file (such
        as a maya scene or katana file, for example), has many external dependencies
        (such as texture files, alembic, etc), those depencies could possibly be 
        changed on disk by the time the uploader get a chance to upload them to Conductor. 
        As a compromise on attempting to create an exact snapshot of the state 
        of ALL files on disk (i.e. md5 hashes)that a job requires at the moment 
        the artist presses "submit", Conductor only guarantees exact file integrity
        on the source file (maya/katana file).  That source file's dependencies
        are NOT guaranteed to match md5s.  In otherwords, a texture file or alembic cache file
        is not md5 checked to ensure it matches the md5 of when the user pressed
        "submit".  Only the maya file is.       
        '''
        # Create a list of files that we want to guarantee to be in the same
        # state when uploading to conductor.  These files will need to md5 hashed here/now.
        # This is potentially TIME CONSUMING (if the files are large and plenty).
        enforced_files = []
        enforced_files.append(self.getSourceFilepath())

        # Generate md5s to dictionary
        enforced_md5s = {}
        for filepath in enforced_files:
            logger.info("md5 hashing: %s", filepath)
            enforced_md5s[filepath] = common.generate_md5(filepath, base_64=True)

        return enforced_md5s

    def getDefaultScoutFrames(self):
        '''
        Return the default scout frames for the open scene file.  This should
        attempt to return the first, middle, and last frame 
        Logic order:
            1. If the "start" and "end" fields are active/populated in the submitter UI
               then use that range to determine first, middle, last scout frames
            2. If the use has specified a custom frame range in the submitter UI,
               Then return None 
        '''
        try:
            if self.ui_start_end_rdbtn.isChecked():
                start = self.getStartFrame()
                end = self.getEndFrame()
                middle = int((float(start) + float(end)) / 2)
                frames = sorted(set([int(start), int(middle), int(end)]))
                scout_frames_str = ", ".join([str(f) for f in frames])
                return scout_frames_str
        except:
            logger.warning("Failed to load default scout frames\n%s", traceback.format_exc())

        # If there is failure or we can't derive the frame range, simply return empty string
        return ""

    def getScoutFrames(self):
        '''
        If the "Scout Job" checkbox is checked, promput the user to ender desired scout frames.
        If the user has submitted scout frames in the past, then prepopulate those frames
        in the dialog box. Otherwise generate default scout frames
        '''

        # If the button that was pressed was the submit_job button (not the submit scout job button)
        if self.getScoutJobCheckbox():

            source_filepath = self.getSourceFilepath()

            # Retrieve any scout frames from the user's prefs, or use defaults
            default_scout_frames = self.prefs.getFileScoutFrames(source_filepath) or self.getDefaultScoutFrames()

            # Launch the scout frames input dialog
            ok, scout_frames = self.launchScoutFramesDialog(default_scout_frames)

            # if the user cancelled
            if not ok:
                raise Exception("Cancelled")  # todo:(lws) Should handle this more gracefully. Probably raise custom exception

            # Record the scout frames specified to the user prefs
            self.prefs.setFileScoutFrames(source_filepath, scout_frames)
            return scout_frames


    def launchScoutFramesDialog(self, default_scout_frames):
        '''
        Launch a dialog box to prompt the user to enter their desired scout
        frames.  Prepopulate the lineedit field with any scout frames that have 
        been submitted previous for the current file (read from preferences). 
        '''
        lineedit_tooltip = ("Specify desired scout frames:\n"
                 "    - individual frame(s), e.g \"1001, 1006\"\n"
                 "    - frame range, e.g \"1001-1006\"\n"
                 "    - frame range with frame skipping. e.g: \"1001-1006x2\"\n"
                 "    - or a mixture, e.g \"1001, 1005-1010, 1020-1030x5\"")

        title = "Scout Frames"
        label_txt = "Designate Scout frames"
        dialog_tooltip = self.ui_scout_job_chkbx.toolTip()



        # Create the dialog's widgets
        dialog = QtGui.QDialog(self)
        verticalLayout = QtGui.QVBoxLayout(dialog)
        label = QtGui.QLabel(dialog)
        verticalLayout.addWidget(label)
        lineedit = QtGui.QLineEdit(dialog)
        verticalLayout.addWidget(lineedit)
        widget = QtGui.QWidget(dialog)
        horizontalLayout = QtGui.QHBoxLayout(widget)
        horizontalLayout.setContentsMargins(0, 0, 0, 0)
        cancel_pbtn = QtGui.QPushButton(widget)
        horizontalLayout.addWidget(cancel_pbtn)
        ok_btn = QtGui.QPushButton(widget)
        horizontalLayout.addWidget(ok_btn)
        verticalLayout.addWidget(widget)
        dialog.layout().setSizeConstraint(QtGui.QLayout.SetFixedSize)

        def _validateScoutFramesText(text):
            '''
            Validation callback
            '''
            if not text or self.frame_str_validator.validate(text, len(text))[0] == QtGui.QValidator.Invalid:
                style_sheet = "background-color: rgb(130, 63, 63);"
            else:
                style_sheet = ""
            # Get the lineedit widget that called this validator
            lineedit.setStyleSheet(style_sheet)
            ok_btn.setDisabled(bool(style_sheet))

        # Connect signals
        lineedit.textChanged.connect(_validateScoutFramesText)
        ok_btn.clicked.connect(dialog.accept)
        cancel_pbtn.clicked.connect(dialog.reject)

        # Trigger the validator immediately so that an empty lineedit will be validated against
        lineedit.textChanged.emit(lineedit.text())

        # Set the widets' texts
        dialog.setWindowTitle(title)
        label.setText(label_txt)
        lineedit.setText(default_scout_frames)
        lineedit.setToolTip(lineedit_tooltip)
        cancel_pbtn.setText("Cancel")
        ok_btn.setText("OK")
        dialog.setToolTip(dialog_tooltip)

        ok = dialog.exec_()
        scout_frames = lineedit.text()
        return ok, scout_frames


    def saveScoutJobPref(self, is_checked):
        '''
        Save the "Scout Job" checkbox user preference for the open file
        '''
        filepath = self.getSourceFilepath()
        self.prefs.setFileUseScoutJob(filepath, bool(is_checked))


    def LoadScoutJobCheckboxPreference(self):
        '''
        Query the user settings for the Scout Job checkbox (whether they explictly
        set it on or off) and apply that setting.  Otherwise, leave the checkbox
        to its default state.
        '''
        filepath = self.getSourceFilepath()
        use_scout_frames = self.prefs.getFileUseScoutJob(filepath)
        if use_scout_frames != None:
            self.setScoutJobCheckbox(bool(use_scout_frames))

class SubmitterPrefs(pyside_utils.UiFilePrefs):

    '''
    A class for interfacing with User preferences for the submitter UI.  
    This subclasses adds functionality that is specific to the Conductor submitter. 
    
    Preference names:
        noremind-scoutframes # bool. Reminder about using scout frames  
        file_submitted       # bool. `A Records whether a file has been submitted or not
        
    Things to consider:
        1. Because preferences are optional/"superflous" they should NEVER break 
           the submitter UI. Therefore all pref reading/writing needs to be 
           safegaurded against(i.e. try/except) so that it doesn't halt usage.
        2. Because the getting/setting of a preference may fail, be sure to model
           preferences in a way so that they will not result in dangerous behavior
           if they fail. i.e. don't allow the absense of a preference value cause
           the user to default to doing something dangerous (such as submit a 
           high frame/corecount job) 
    
    '''
    # PREFERENCE NAMES (these the names that are used/written to the preference file
    PREF_SCOUTFRAMES_STR = "scoutframes_str"
    PREF_SCOUTFRAMES_ON = "scoutframes-ON"

    @common.ExceptionLogger("Failed to load Conductor user preferences. You may want to reset your preferences from the options menu")
    def loadSubmitterUserPrefs(self, source_filepath):
        '''
        Load both the global and file-specific (e.g.nuke/maya file) user 
        preferences for the UI widgets. This will reinstate any values on the
        widgets that that were recorded on them from the last time. 
        
        First load the global preferences, then load the file-specific prefs
        which will override and of the global prefs
        '''
        # Load the global prefs
        self.loadGlobalWidgetPrefs()

        # Load the file-specific prefs
        self.loadFileWidgetPrefs(source_filepath)

    @common.ExceptionLogger("Failed to save Conductor user preferences. You may want to reset your preferences from the options menu")
    def saveSubmitterUserPrefs(self, source_filepath):
        '''
        Save current widget settings to the user's preference file.  These settings
        are recorded per source file (maya/katana/nuke file, etc).
        '''
        # Save the global prefs
        self.saveGlobalWidgetPrefs()

        # Save the file-specific prefs
        self.saveFileWidgetPrefs(source_filepath)

    @common.ExceptionLogger("Failed to load Conductor user preferences. You may want to reset your preferences from the options menu")
    def getFileScoutFrames(self, filepath):
        '''
        Return the user settings for:
            the frame/range to use for scout frames
        '''
        return self.getPref(self.PREF_SCOUTFRAMES_STR, filepath=filepath)


    @common.ExceptionLogger("Failed to save Conductor user preferences. You may want to reset your preferences from the options menu")
    def setFileScoutFrames(self, filepath, value):

        '''
        Set the user settings for:
            the frame/range to use for scout frames
        '''
        return self.setPref(self.PREF_SCOUTFRAMES_STR, value, filepath=filepath)

    @common.ExceptionLogger("Failed to load Conductor user preferences. You may want to reset your preferences from the options menu")
    def getFileUseScoutJob(self, filepath):
        '''
        Return the user settings for:
           the value of the "Scout Job" checkbox that the user applied
           for the given file.
        '''
        return self.getPref(self.PREF_SCOUTFRAMES_ON, filepath=filepath)


    @common.ExceptionLogger("Failed to save Conductor user preferences. You may want to reset your preferences from the options menu")
    def setFileUseScoutJob(self, filepath, value):

        '''
        Set the user settings for:
           the value of the "Scout Job" checkbox for the given file.
        '''
        return self.setPref(self.PREF_SCOUTFRAMES_ON, value, filepath=filepath)


if __name__ == "__main__":
    app = QtGui.QApplication.instance()
    if app is None:
        app = QtGui.QApplication(sys.argv)
    ConductorSubmitter.runUi()
