from collections import defaultdict as DefaultDict
import functools
import imp
from itertools import groupby
import logging
import os
import operator
from pprint import pformat
from Qt import QtGui, QtCore, QtWidgets, QtCompat
import sys
import traceback
from conductor.lib.lsseq import seqLister

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conductor import CONFIG

from conductor.lib import api_client, common, conductor_submit, exceptions, loggeria, package_utils, pyside_utils
from conductor import submitter_resources  # This is a required import  so that when the .ui file is loaded, any resources that it uses from the qrc resource file will be found

PACKAGE_DIRPATH = os.path.dirname(__file__)
RESOURCES_DIRPATH = os.path.join(PACKAGE_DIRPATH, "resources")
SUCCESS_CODES_SUBMIT = [201, 204]
TASK_CONFIRMATION_THRESHOLD = 1000

logger = logging.getLogger(__name__)

# Store the parent window so that we can reuse it later
_parent_window = None

# Store the submitter instance so that we can reuse it later (re-open a closed window)
_ui_instance = None

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


class ConductorSubmitter(QtWidgets.QMainWindow):
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

    link_color = "rgb(200,100,100)"

    software_packages = None

    product = None

    _job_software_tab_idx = 2

    def __init__(self, parent=None):
        '''
        1. Load the ui file
        2. Initialize widgets (set behavior, populate options, resize/reformat)
        3. Load any user settings to restore widget values from user preferences
        '''
        super(ConductorSubmitter, self).__init__(parent=parent)
        pyside_utils.UiLoader.loadUi(self._ui_filepath, self)

        # Create widgets
        self.createUi()

        # Instantiate a user prefs  object
        self.prefs = SubmitterPrefs(company_name=self.company_name,
                                    application_name=self.__class__.__name__,
                                    file_widgets=self.getUserPrefsFileWidgets(),
                                    global_widgets=self.getUserPrefsGlobalWidgets())
        # Populate the UI with info
        self.populateUi()

        # Apply default settings
        self.applyDefaultSettings()

        # Load user preferences over top of default settings
        self.loadUserSettings()

    @classmethod
    @pyside_utils.wait_cursor
    def runUi(cls, force_new=False):
        '''
        Launch the submitter UI.
        By default, this will reuse/show any previously instantiated submitter object (as opposed to
        creating a new instance). Use the `force_new` flag to force a new instance of it.
        '''
        global _parent_window  # This global statement is particularly important (though it may not appear so when using simple usecases that don't use complex inheritence structures).
        global _ui_instance

        # Reuse the same parent window object, otherwise ownshership gets
        # jacked, and child widgets start getting deleted. This took about 3
        # hours to figure out.
        if not _parent_window:
            _parent_window = cls.getParentWindow()

        # if there is an existing instance of the window, simply show it.
        if not force_new and _ui_instance:
            logger.debug("Reopening existing Submitter window")
            _ui_instance.show()

            # Apply default settings to UI
            _ui_instance.applyDefaultSettings()

            # load the user settings because the open file may have changed
            _ui_instance.loadUserSettings()
        else:
            logger.debug("Creating new Submitter window")

            # Otherwise create a new instance
            _ui_instance = cls(parent=_parent_window)
            _ui_instance.show()

        # Bring focus to this window
        _ui_instance.activateWindow()

        return _ui_instance

    @classmethod
    def getParentWindow(cls):
        '''
        Return a QtWidget object that should act as the parent for the submitter
        window. This is oftentime the case when launching the submitter within
        another application such as nuke or maya.  In these cases, return
        the main QtWindow object for those applications.
        '''
        return None

    def createUi(self):
        '''
        Create UI widgets and make
        '''

        # Set the start/end fields to be restricted to integers only
        self.ui_start_frame_lnedt.setValidator(QtGui.QIntValidator())
        self.ui_end_frame_lnedt.setValidator(QtGui.QIntValidator())

        # Set string validation for the custom frame range field
        self._setCustomRangeValidator()
        self.ui_custom_lnedt.textChanged.connect(self._validateCustomFramesText)

        # connect the scout job checkbox signal
        self.ui_scout_job_chkbx.stateChanged.connect(self.saveScoutJobPref)

        # Add the Instance Options widget
        self._addInstanceOptionsWidget()

        # Set the window title name
        self.setWindowTitle(self._window_title)

        # Setup the top menu bar
        self.setupMenuBar()

        # Hide find button (until maybe a later release TODO:(LWS) Come back to this
        self.ui_find_pbtn.hide()

        # Connect context menu for job software treewidget
        self.ui_job_software_trwgt.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui_job_software_trwgt.customContextMenuRequested.connect(self.openJobTreeMenu)

        # Connect context menu for available software treewidget
        self.ui_software_versions_trwgt.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.ui_software_versions_trwgt.customContextMenuRequested.connect(self.openAvailableTreeMenu)

        self.ui_packages_splitter.setStretchFactor(0, 1)
        self.ui_packages_splitter.setStretchFactor(1, 2)

        # Hide the widget that holds advanced settings. TODO: need to come back to this.
        self.ui_advanced_wgt.hide()

        # Add the extended widget (must be implemented by the child class
        self._addExtendedWidget()

        # Add the advanded extended widget (must be implemented by the child class)
        self._addExtendedAdvancedWidget()

    def populateUi(self):
        '''
        Populate the UI with data.  This data should be global information that
        is not specific to the open file
        '''
        # Populate the software versions tree widget
        self.populateSoftwareVersionsTrWgt()

        # Populate the Project combobox with customer's projects
        self.populateProjectCmbx()

    def applyDefaultSettings(self):
        '''
        Set the UI to default settings.
        '''

        # Set the radio button on for the start/end frames by default
        self.on_ui_start_end_rdbtn_toggled(True)

        # Set the default project by querying the config
        default_project = CONFIG.get('project')
        if default_project:
            self.setProject(default_project, strict=False)

        # Show only available packages in accordance with the checkbox
        self.filterPackages(show_all_versions=self.ui_show_all_versions_chkbx.isChecked())

        # Set scout Job checkbox ON by default.
        self.ui_scout_job_chkbx.blockSignals(True)
        self.ui_scout_job_chkbx.setChecked(True)
        self.ui_scout_job_chkbx.blockSignals(False)

        # Populate the Job packages treewidget (this is file specific so goes in this function, rather than self.populateUi
        self.populateJobPackages()

        # Set the keyboard focus on the frame range radio button
        self.ui_start_end_rdbtn.setFocus()

    def _addInstanceOptionsWidget(self):
        '''
        Add the Instance Options widget to the UI
        '''
        self.instance_options_wgt = self.getInstanceOptionsWidget()
        if self.instance_options_wgt:
            instance_widget_layout = self.ui_instance_container_wgt.layout()
            instance_widget_layout.addWidget(self.instance_options_wgt)

            # connect the preemptible checkbox signal to save state to prefs
            self.instance_options_wgt.ui_preemptible_chkbx.stateChanged.connect(self.savePreemptiblePref)

    def _addExtendedWidget(self):
        '''
        Add the extended widget to the UI
        '''
        self.extended_widget = self.getExtendedWidget()
        if self.extended_widget:
            extended_widget_layout = self.ui_extended_container_wgt.layout()
            extended_widget_layout.addWidget(self.extended_widget)

    def _addExtendedAdvancedWidget(self):
        '''
        Add the extended advanced widget to the UI if one has been defined (via subclass)
        '''
        self.extended_advanced_widget = self.getExtendedAdvancedWidget()
        if self.extended_advanced_widget:
            layout = self.ui_extended_advanced_container_wgt.layout()
            layout.addWidget(self.extended_advanced_widget)

    def getInstanceOptionsWidget(self):
        '''
        Instantiate and return the InstanceOptions widget.  This widget is responsible
        for presenting instance type options to the user.
                 ________________________
                |      General <tab>     |
                |------------------------|
                |      Frame Range       |
                |------------------------|
                | <INSTANCE OPTS WIDGET> |   <-- here
                |------------------------|
                |    extended widget     |
                |------------------------|
                |     submit button      |
                |________________________|

        '''
        # Request all of the instance types from conductor service
        instance_types = api_client.request_instance_types()
        # Instantiated and return the widget
        return InstanceOptionsWidget(instance_types)

    def getExtendedWidget(self):
        '''
        This method extends the Conductor UI by providing a single PySide widget
        that will be added to the UI. The widget may be any class object derived
        from QWidget.

        In order to do so, subclass this class and override this method to
        return the desired widget object.  This widget will be inserted between
        the Frame Range area and the  Submit button. See illustration below:

                 ________________________
                |      General <tab>     |
                |------------------------|
                |      Frame Range       |
                |------------------------|
                |    Instance Options    |
                |------------------------|
                |    <EXTENDED WIDGET>   |   <-- here
                |------------------------|
                |     submit button      |
                |________________________|

        '''

    def getExtendedAdvancedWidget(self):
        '''
        This method extends the Conductor UI by providing a single PySide widget
        that will be added to the UI. The widget may be any class object derived
        from QWidget.

        In order to do so, subclass this class and override this method to
        return the desired widget object.  This widget will be inserted at the bottom
        of the "Advanced" tab. See illustration below:

                 ____________________
                |   Advanced <tab>   |
                |--------------------|
                |                    |
                |                    |
                |                    |
                |--------------------|
                |                    |
                |  <EXTENDED WIDGET> |   <-- here
                |____________________|

        '''

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

    @staticmethod
    def addLoggingMenu(menu):
        '''
        For the given menu object, dynamically generate a action item for
        each log level (from the loggeria module).
        '''
        conductor_logger = loggeria.get_conductor_logger()
        current_level = conductor_logger.level

        # Create an action group (this allows for mutually exclusive checkboxes (radio buttons)
        action_group = QtWidgets.QActionGroup(menu)

        # loop by order of log_level value
        for level_name, level_value in sorted(loggeria.LEVEL_MAP.iteritems(),
                                              key=operator.itemgetter(1), reverse=True):
            # Generate the function that the menu action will call
            func = functools.partial(loggeria.set_conductor_log_level, log_level=level_name)
            action = menu.addAction(level_name, func)
            action.setCheckable(True)
            # Set the action item to be checked if its log level matches the current log level
            action.setChecked(current_level == level_value)
            action_group.addAction(action)

    def addResetPreferencesMenu(self, menu):
        '''
        For the given menu object, dynamically generate a action item for
        each log level (from the loggeria module).
        '''

        # RESET ALL PREFERENCES
        action_name = "Global Preferences"
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
                                                   show_not_again_checkbox=False,
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

    def populateProjectCmbx(self):
        '''
        Populate the project combobox with project names.  If any projects are
        specified in the config file, then use them. Otherwise query Conductor
        for all projects
        '''
        self.ui_project_cmbx.clear()
        projects = CONFIG.get("projects") or api_client.request_projects()
        # sort alphabetically. may be unicode, so can't use str.lower directly
        for project in sorted(projects, key=lambda x: x.lower()):
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

    def setChunkSize(self, chunk_size):
        '''
        Set the UI's Frame Chunk Size spinbox value
        '''
        self.ui_chunk_size_spnbx.setValue(int(chunk_size))

    def getChunkSize(self):
        '''
        Return UI's Frame Chunk Size spinbox value
        '''
        return self.ui_chunk_size_spnbx.value()

    def setProject(self, project_str, strict=True):
        '''
        Set the UI's Project field
        '''
        index = self.ui_project_cmbx.findText(project_str)
        if index == -1:
            msg = "Project combobox entry does not exist: %s" % project_str
            logger.warning(msg)
            if strict:
                raise Exception(msg)

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
        Query the UI's Notification field and split string on commas, returning
        a list of email addresses
        '''
        notify_str = str(self.ui_notify_lnedt.text())
        return [email.strip() for email in notify_str.split(",") if email.strip()]

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

        conductor_args["environment"] = self.getEnvironment()
        conductor_args["force"] = self.getForceUploadBool()
        conductor_args["chunk_size"] = self.getChunkSize()
        conductor_args["instance_type"] = self.instance_options_wgt.getInstanceType()
        conductor_args["job_title"] = self.getJobTitle()
        conductor_args["local_upload"] = self.getLocalUpload()
        conductor_args["preemptible"] = self.instance_options_wgt.getPreemptibleCheckbox()
        conductor_args["notify"] = self.getNotifications()
        conductor_args["output_path"] = self.getOutputDir()
        conductor_args["project"] = self.getProject()
        conductor_args["scout_frames"] = self.getScoutFrames()
        conductor_args["software_package_ids"] = self.getSoftwarePackageIds()
        conductor_args["autoretry_policy"] = self.instance_options_wgt.getAutoretryPolicy()

        return conductor_args

    def getDockerImage(self):
        '''
        Return the Docker image name to use on Conductor.

        If there is a docker image in the config.yml file, then use it.
        '''

        return CONFIG.get("docker_image")

    def getEnvironment(self):
        '''
        Return a dictionary of environment variables to use for the Job's
        environment. Merge any environment settings defined in the config with
        the environment of the packages that the user has selected.
        '''
        #  Get any environment variable settings from config.yml
        config_environment = CONFIG.get("environment") or {}
        assert isinstance(config_environment, dict), "Not a dictionary: %s" % config_environment
        selected_packages = self.getJobPackages()
        return package_utils.merge_package_environments(selected_packages,
                                                        base_env=config_environment)

    def getSoftwarePackageIds(self):
        '''
        Return the software packages that the submitted job will have access to
        when running.  These packages are referred to by their ids. Merge the
        any packages that are defined in the config with those that are selected
        by the user.
        '''
        config_package_ids = CONFIG.get("software_package_ids") or []
        assert isinstance(config_package_ids, list), "Not a list: %s" % config_package_ids
        selected_package_ids = [package["package_id"] for package in self.getJobPackages()]
        return list(set(config_package_ids + selected_package_ids))

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

        except BaseException:
            title = "Job submission failure"
            message = "".join(traceback.format_exception(*sys.exc_info()))
            pyside_utils.launch_error_box(title, message, self)
            raise
        return response_code, response

    @staticmethod
    def getLocalUpload():
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
            job_url = CONFIG['auth_url'] + "/job/" + job_id
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
        try:
            if not self.validateJobPackages():
                return
            if not self.checkJobSize():
                return

            data = self.runPreSubmission()
            if data:
                response_code, response = self.runConductorSubmission(data)
                self.runPostSubmission(response_code)

                # Launch a dialog box what diesplays the results of the job submission
                self.launch_result_dialog(response_code, response)

        except exceptions.UserCanceledError:
            logger.info("Canceled by user")

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

    @pyside_utils.wait_cursor
    @QtCore.Slot(name="on_ui_refresh_tbtn_clicked")
    def on_ui_refresh_tbtn_clicked(self):
        self.applyDefaultSettings()

    @QtCore.Slot(name="on_ui_choose_output_path_pbtn_clicked")
    def on_ui_choose_output_path_pbtn_clicked(self):

        dirpath = str(QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory"))
        if dirpath:
            self.setOutputDir(dirpath)

    def getFrameRangeString(self):
        '''
        Construct the frameRange string for the frames argument
        '''
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
        Return the filepath for the currently open file. This is the currently opened 
        maya/katana/nuke file, etc
        '''

    def loadUserSettings(self):
        '''
        Read and apply user preferences (widget values, etc)
        '''
        try:
            self.prefs.sync()
            source_filepath = self.getSourceFilepath()
            self.prefs.loadSubmitterUserPrefs(source_filepath=source_filepath)
        except BaseException:
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
            self.saveJobPackagesToPrefs()
            source_filepath = self.getSourceFilepath()
            self.prefs.saveSubmitterUserPrefs(source_filepath)
            self.prefs.sync()
        except BaseException:
            logger.exception("Unable to save user settings:")

    @pyside_utils.wait_cursor
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
        this dictionary, and match it against the md5s that the dictionary provides.
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
        except BaseException:
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
                raise exceptions.UserCanceledError()

            # Record the scout frames specified to the user prefs
            self.prefs.setFileScoutFrames(source_filepath, scout_frames)
            return scout_frames

    def checkJobSize(self):
        """
        Make sure the user is aware they are about submit a large job.

        A large job has more tasks than a threshold. 
        We first test the number of frames, because calculating 
        the number of tasks is slow. If frames length is below the
        threshold, then there can't possibly be too many tasks. If 
        there are too many tasks, then show the confirmation dialog.

        """
        logger.debug("Check job size")
        frames_str = self.getFrameRangeString()
        frames = seqLister.expandSeq(frames_str.split(","), None)
        if len(frames) < TASK_CONFIRMATION_THRESHOLD:
            return True
        chunk_size = self.getChunkSize()

        # To count the tasks, we have to make a generator and sum 1 for every yield
        task_counter = TaskFramesGenerator(frames, chunk_size=chunk_size, uniform_chunk_step=True)
        task_count = sum(1 for _ in task_counter)

        if task_count < TASK_CONFIRMATION_THRESHOLD:
            return True

        logger.debug("{} is {:d} frames divided into chunks of {:d}".format(
            frames_str,
            len(frames),
            chunk_size)
        )
        logger.debug("Confirm submission of {} tasks".format(task_count))

        title = "Warning: Large Job!"

        message = """<html><head/><body>
        <p>You are about to submit {} tasks.</p>
        <p><strong>Are you sure?</strong></p>
        </body></html>
        """.format(task_count)

        sure, _ = pyside_utils.launch_yes_no_dialog(
            title, message, show_not_again_checkbox=False, parent=None)

        log_msg = "Confirmed submission of a very large job" if sure else "Canceled large job"
        logger.info(log_msg)
        return sure

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
        dialog = QtWidgets.QDialog(self)
        verticalLayout = QtWidgets.QVBoxLayout(dialog)
        label = QtWidgets.QLabel(dialog)
        verticalLayout.addWidget(label)
        lineedit = QtWidgets.QLineEdit(dialog)
        verticalLayout.addWidget(lineedit)
        widget = QtWidgets.QWidget(dialog)
        horizontalLayout = QtWidgets.QHBoxLayout(widget)
        horizontalLayout.setContentsMargins(0, 0, 0, 0)
        cancel_pbtn = QtWidgets.QPushButton(widget)
        horizontalLayout.addWidget(cancel_pbtn)
        ok_btn = QtWidgets.QPushButton(widget)
        horizontalLayout.addWidget(ok_btn)
        verticalLayout.addWidget(widget)
        dialog.layout().setSizeConstraint(QtWidgets.QLayout.SetFixedSize)

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

    @common.ExceptionLogger("Failed to save Conductor user preferences. You may want to reset your preferences from the options menu")
    def saveScoutJobPref(self, is_checked):
        '''
        Save the "Scout Job" checkbox user preference for the open file
        '''
        filepath = self.getSourceFilepath()
        widget_name = self.sender().objectName()
        return self.prefs.setFileWidgetPref(filepath, widget_name, bool(is_checked))

    @common.ExceptionLogger("Failed to save Conductor user preferences. You may want to reset your preferences from the options menu")
    def savePreemptiblePref(self, is_checked):
        '''
        Save the "Preemptible" checkbox user preference for the open file
        '''
        filepath = self.getSourceFilepath()
        widget_name = self.sender().objectName()
        return self.prefs.setFileWidgetPref(filepath, widget_name, bool(is_checked))

    ###########################################################################
    #  SOFTWARE PACKAGES
    ###########################################################################

    def getHostProductInfo(self):
        '''
        If this ui is running within a host application (e.g. as a plugin for Maya), this method
        should be overridden to provide a dictionary of the host application's product information,
        e.g.
            {"product": "maya",
             "version": ,
             "package_id": package_id}
        '''

    def getPluginsProductInfo(self):
        return []

    def introspectSoftwareInfo(self):
        '''
        Introspect the current runtime environment (whether that be within Maya, Nuke, or a
        standalone python shell), and return a any product information that can be used to match
        against available packages on conductor.  In order for the matching to occur, the collected
        product information must be constructed as a similar format as conductor's own packages.
        '''
        host_product_info = self.getHostProductInfo()
        plugin_products_info = self.getPluginsProductInfo()
        return filter(None, [host_product_info] + plugin_products_info)

    def populateJobPackages(self, auto=False):
        '''
        1. query the prefs for package ids
        2. Query the config for package ids and add
        3. if none, then auto detect

        '''
        self.ui_job_software_trwgt.clear()
        source_filepath = self.getSourceFilepath()
        software_package_ids = self.prefs.getJobPackagesIds(source_filepath) or []

        # Hack for pyside. If there is only one package id, it will return it as unicode type (rather than a lost of 1 string)
        if isinstance(software_package_ids, unicode):
            software_package_ids = [str(software_package_ids)]
        software_package_ids += (CONFIG.get("software_package_ids") or [])

        # If no packages have been found in prefs or config, then autodetect packages
        if not software_package_ids:
            software_package_ids = self.autoDetectPackageIds()

        # get the package dictionaries from their package id
        software_packages = filter(None, [self.software_packages.get(package_id) for package_id in set(software_package_ids)])

        # if there are any packages, then populate the treewidget with them
        if software_packages:
            self.populateJobSoftwareTrwgt(software_packages)

    def autoPopulateJobPackages(self):
        self.ui_job_software_trwgt.clear()
        package_ids = self.autoDetectPackageIds()

        software_packages = filter(None, [self.software_packages.get(package_id) for package_id in package_ids])
        if software_packages:
            self.populateJobSoftwareTrwgt(software_packages)

    def autoDetectPackageIds(self):
        '''
        Of the given packages, return the packages that match

        1. host software
        2. plugins
            - renderer
            - others
        '''

        softwares_info = self.introspectSoftwareInfo()

        matched_packages = []
        unmatched_software = []
        for software_info in softwares_info:
            # package_item = self.getBestPackage(software_info, tree_packages)
            package_id = software_info.get("package_id")
            package = self.software_packages.get(package_id)
            if not package:
                unmatched_software.append(software_info)
            else:
                matched_packages.append(package_id)

        if unmatched_software:
            msg = "Could not match software info: \n\t%s" % ("\n\t".join([pformat(s) for s in unmatched_software]))
            logger.warning(msg)
            package_strs = ["- %s: %s %s" % (p["product"], p["version"], "(for %s: %s)" % (p["host_product"], p["host_version"]) if p.get("host_product") else "")
                            for p in unmatched_software]
            msg = "The following software packages could not be auto matched:\n  %s" % "\n  ".join(package_strs)
            msg += '\n\nManually add desired software packages in the "Job Software" tab'

            title = "Software Package Error"
            pyside_utils.launch_error_box(title, msg, parent=self)
            self.ui_tabwgt.setCurrentIndex(self._job_software_tab_idx)

        return matched_packages

    def saveJobPackagesToPrefs(self):
        package_ids = []
        for item in pyside_utils.get_top_level_items(self.ui_job_software_trwgt):
            package_ids.append(item.package_id)
        filepath = self.getSourceFilepath()
        self.prefs.setJobPackagesIds(filepath, package_ids)

    ###########################################################################
    #  AVAILABLE SOFTWARE TREEWIDGET  - self.ui_software_versions_trwgt
    ###########################################################################

    @QtCore.Slot(name="on_ui_add_to_job_pbtn_clicked")
    def on_ui_add_to_job_pbtn_clicked(self):
        self._availableAddSelectedItems()
        self.validateJobPackages()
        self.saveJobPackagesToPrefs()

    @QtCore.Slot(name="on_ui_show_all_versions_chkbx_clicked")
    def on_ui_show_all_versions_chkbx_clicked(self):

        self.filterPackages(show_all_versions=self.ui_show_all_versions_chkbx.isChecked())

    def populateSoftwareVersionsTrWgt(self):
        '''
        Populate the QTreeWidget with all of the available software packages

        This is a little tricky because packages can be plugins of other packages,
        and we want to represent that relations (via nesting).  We also want
        to group packages that are of the same type (and have them be able to
        expand/collpase that group.


        Here is an example hierarchy:

            maya  # The group for all maya version packages
                |
                |_maya 2014 SP1  # The actual package
                        |
                        |_vray  # The group for all vray packages (for maya 2014 SP1)
                                |
                                |_vray 1.2.4 # The actual package
                        |
                        |_arnold # The group for all arnold packages (for maya 2014 sp1)
                                |
                                |_arnold 2.73.1 # The actual package
                |
                |_maya 2014 SP2  # The actual package
                        |
                        |_vray  # The group for all vray packages (for maya 2014 SP2)
                                |
                                |_vray 1.2.4   # The actual package
                        |
                        |_arnold # The group for all Arnold packages (for maya 2014 SP2)
                                |
                                |_arnold 2.73.1  # The actual package



        A package's data structure may look like this:

           {"package_id": "6b24ca0ea1085ebad536c18307192dce"
            "product": "maya",
            "major_version": "2015",
            "minor_version": "SP3",
            "release_version": "",
            "build_version": "",
            "plugin_host_product": "",
            "plugin_host_version": "",
            "plugin_hosts": [],
            "plugins": [  "8ac98ef9362171a889c5ac8dca8a2a47",
                          "03be394b4f84ec9a0d86e4b6f5f3fe26",
                          "86779e759adcbbd38e1d058125ace737"]}

        '''
        self.ui_software_versions_trwgt.clear()

        # Query Conductor for all of it's software packages
        software_packages = api_client.request_software_packages()

        # Create a dictioary of the software packages so that they can be retried by ID
        self.software_packages = dict([(package["package_id"], package) for package in software_packages])

        # Get packages that are host packages (i.e. not plugins). This is the "top" of the hierarchy
        host_packages = [package for package in self.software_packages.values() if not package["plugin_host_product"]]

        # Create a tree item for every package (we'll group/parent them later)
        # TODO:(LWS) This really ought to be a more clever recursive function.
        # This is currently hard coded for only two depth levels.
        for host_package in host_packages:

            # HOST PRODUCT PACKAGE ###
            host_package_item = self.createPackageTreeWidgetItem(host_package)
            self.ui_software_versions_trwgt.addTopLevelItem(host_package_item)

            # # PLUGINS FOR PRODUCT ##
            plugin_parent_items = {}
            for plugin_id in host_package["plugins"]:
                plugin_package = self.software_packages.get(plugin_id)
                if not plugin_package:
                    logger.warning("Not able to find expected plugin. Id: %s", plugin_id)
                    continue

                # PLUGIN PRODUCT GROUP ####
                plugin_product_name = plugin_package["product"]
                plugin_parent_product_item = plugin_parent_items.get(plugin_product_name)
                if not plugin_parent_product_item:
                    plugin_parent_product_item = QtWidgets.QTreeWidgetItem([plugin_product_name, ""])
                    plugin_parent_product_item.setFlags(QtCore.Qt.ItemIsEnabled)
                    plugin_parent_product_item.product = plugin_product_name
                    plugin_parent_items[plugin_product_name] = plugin_parent_product_item
                    host_package_item.addChild(plugin_parent_product_item)

                # PLUGIN PRODUCT PACKAGE ###
                plugin_package_item = self.createPackageTreeWidgetItem(plugin_package)
                plugin_parent_product_item.addChild(plugin_package_item)

        # Sort the row by the version column
        software_column_idx = 1
        self.ui_software_versions_trwgt.sortByColumn(software_column_idx, QtCore.Qt.AscendingOrder)

    # THIS IS COMMENTED OUT UNTIL WE DO DYNAMIC PACKAGE LOOKUP
#     def filterPackages(self, show_all_versions=False):
#         host_product_info = self.getHostProductInfo()
# #         item_groups = self.getTreeItemGroups()
#         for host_package_item in self.getHostPackageTreeItems():
#             self.ui_software_versions_trwgt.setItemHidden(host_package_item, True)
#             package = self.get_package_by_id(host_package_item.package_id)
#             if package["product"] == self.product:
#                 best_package = self.getBestPackage(host_product_info, self.software_packages.values())
#                 if show_all_versions or (best_package and package["package_id"] == best_package["package_id"]):
#                     self.ui_software_versions_trwgt.setItemHidden(host_package_item, False)

    def filterPackages(self, show_all_versions=False):
        '''
        Filter the packages in the software treewidget to show only those correspond to the 
        host software product and version.
        '''
        # Get information about the host application
        host_package_info = self.getHostProductInfo()

        # If there's no host information, then there's no filtering to be done. Show all packages.
        if not host_package_info:
            return

        # otherwise filter by the host package info
        host_package_id = host_package_info["package_id"]
        host_package = self.get_package_by_id(host_package_id) if host_package_id else None

        for host_package_item in self.getHostPackageTreeItems():
            package = self.get_package_by_id(host_package_item.package_id)

            # we only show the package if it matches the ui's designated product, and..
            show = package["product"] == self.product and (
                # if no host package was identified (therefore nothing to filter against)
                not host_package or
                # or the package exactly matches the host package version
                package == host_package or
                # or we've been told explicitly to show all package versions for the product
                show_all_versions,
            )
            # hide/show the package (btw, there is no setItemVisible method, so we must use double negative logic)
            self.ui_software_versions_trwgt.setItemHidden(host_package_item, not show)

    def getTreeItemPackages(self):
        tree_item_packages = {}
        for tree_item in pyside_utils.get_all_tree_items(self.ui_software_versions_trwgt):
            if hasattr(tree_item, "package_id"):
                tree_item_packages[tree_item.package_id] = self.get_package_by_id(tree_item.package_id)
        return tree_item_packages

    def getHostPackageTreeItems(self, host_product_name=None):
        host_package_tree_items = []
        for item in pyside_utils.get_top_level_items(self.ui_software_versions_trwgt):
            package = self.get_package_by_id(item.package_id)
            if not host_product_name or host_product_name == package["product"]:
                host_package_tree_items.append(item)
        return host_package_tree_items

#     def getTreeItemGroups(self):
#         tree_item_groups = {}
#         for tree_item in pyside_utils.get_all_tree_items(self.ui_software_versions_trwgt):
#             if hasattr(tree_item, "product"):
#                 tree_item_groups[tree_item] = tree_item.product
#         return tree_item_groups

    def getBestPackage(self, software_info, packages):
        return self.getMatchingPackage(software_info, packages, strict=False)
#         maching_packages = package_utils.get_matching_packages(software_info, packages)
#
#         logger.debug("maching_packages (%s): %s", len(maching_packages), maching_packages)
#
#         if not maching_packages:
#             return
#
#         if len(maching_packages) > 1:
#             raise Exception("More than one matching package found for software: %s\n\t%s" %
#                             (pformat(software_info), "\n\t".join([pformat(p) for p in maching_packages])))
#
#
#         return maching_packages[0]

    def getMatchingPackage(self, software_info, packages, strict=False):
        matching_packages = package_utils.get_matching_packages(software_info, packages)
        if not matching_packages:
            msg = "Could not find matching package of:\n%s" % pformat(software_info)
            logger.debug(msg)
            if strict:
                raise Exception(msg)
            return

        if len(matching_packages) > 1:
            raise Exception("More than one best package found for software: %s\n\t%s" %
                            (pformat(software_info), "\n\t".join([pformat(p) for p in matching_packages])))

        return matching_packages[0]

    @staticmethod
    def createPackageTreeWidgetItem(package):
        '''
        For the given software package, create a QTreeWidgetItem for it.
        with
        a text/name that describes it
        '''

        # This will be used for the "Software Name" column
        software_name = package["product"]

        # Construct the text to give the "Version" column. concatenate all version tiers together
        software_version = ".".join(filter(None, [package.get(v) for v in
                                                  ["major_version",
                                                   "minor_version",
                                                   "release_version",
                                                   "build_version"]]))
        tree_item = QtWidgets.QTreeWidgetItem([software_name, software_version])
        tree_item.package_id = package["package_id"]
        return tree_item

    def getSelectedAvailablePackages(self):
        '''
        Return the package dictionaries for each QTreeItem that is selected by
        the user.
        '''
        selected_packages = []
        for item in self.ui_software_versions_trwgt.selectedItems():
            selected_packages.append(self.get_package_by_id(item.package_id))
        return selected_packages

    def get_package_by_id(self, package_id):
        # This can happen when the local resources files is out of sync with active
	# packages on the back-end
        try:
            software_package = self.software_packages[package_id]
        except KeyError:
            logger.warning("Unable to locate the package {} in the list of packages.".format(package_id))
            return None
        
        return software_package

    def openAvailableTreeMenu(self, position):
        selected_item = self.ui_software_versions_trwgt.itemAt(position)
        menu = self._makeAvalailableSoftwareContextMenu(selected_item)
        menu.exec_(self.ui_software_versions_trwgt.viewport().mapToGlobal(position))

    def _makeAvalailableSoftwareContextMenu(self, selected_item):
        '''
        Remove selected items
        Add selected items
        Show items in (other) tree
        '''
        menu = QtWidgets.QMenu()

        # "check selected" menu item
        menu.addAction("Add selected packages to Job", self._availableAddSelectedItems)
        return menu

    def _availableAddSelectedItems(self):
        selected_available_packages = self.getSelectedAvailablePackages()
        if not selected_available_packages:
            return pyside_utils.launch_error_box(
                "No packages selected", "No packages have been selected."
                "Please select at least one package before adding it to the job.", parent=self)
        for package in selected_available_packages:
            job_package_item = self.createJobPackageTreeWidgetItem(package)
            self.ui_job_software_trwgt.addTopLevelItem(job_package_item)

    def _selectAvailablePackages(self, packages, clear=True):
        tree_items = []
        for tree_item in pyside_utils.get_all_tree_items(self.ui_software_versions_trwgt):
            for package in packages:
                if hasattr(tree_item, "package_id") and tree_item.package_id == package["package_id"]:
                    tree_items.append(tree_item)
        if clear:
            self.ui_software_versions_trwgt.selectionModel().clear()

        for tree_item in tree_items:
            self.ui_software_versions_trwgt.setItemSelected(tree_item, True)

    ###########################################################################
    #  JOB SOFTWARE TREEWIDGET  - self.ui_job_software_trwgt
    ###########################################################################

    @QtCore.Slot(name="on_ui_auto_detect_pbtn_clicked")
    def on_ui_auto_detect_pbtn_clicked(self):
        self.autoPopulateJobPackages()
        self.saveJobPackagesToPrefs()

    @QtCore.Slot(name="on_ui_remove_selected_pbtn_clicked")
    def on_ui_remove_selected_pbtn_clicked(self):
        self._jobRemoveSelectedItems()

    @QtCore.Slot(name="on_ui_find_pbtn_clicked")
    def on_ui_find_pbtn_clicked(self):
        self._jobFindSelectedItemsInAvailableTree()

    def populateJobSoftwareTrwgt(self, packages):
        self.ui_job_software_trwgt.clear()
        for package in packages:
            job_package_item = self.createJobPackageTreeWidgetItem(package)
            self.ui_job_software_trwgt.addTopLevelItem(job_package_item)

    def openJobTreeMenu(self, position):
        selected_item = self.ui_job_software_trwgt.itemAt(position)
        menu = self._makeJobContextMenu(selected_item)
        menu.exec_(self.ui_job_software_trwgt.viewport().mapToGlobal(position))

    def _makeJobContextMenu(self, selected_item):
        '''
        Remove selected items
        Add selected items
        Show items in (other) tree
        '''
        menu = QtWidgets.QMenu()

        # "check selected" menu item
        menu.addAction("Remove selected packages", self._jobRemoveSelectedItems)
        return menu

    def _jobRemoveSelectedItems(self):
        for item in self.ui_job_software_trwgt.selectedItems():
            # indexOfTopLevelItem() is not available in PySide2 2.0.0~alpha0
            # which is the build provided by Maya 2017
            # just mimicked functionality of function see qtreewidget.cpp
            root = self.ui_job_software_trwgt.invisibleRootItem()
            index = root.indexOfChild(item)
            self.ui_job_software_trwgt.takeTopLevelItem(index)
        self.saveJobPackagesToPrefs()

    def _jobFindSelectedItemsInAvailableTree(self):
        job_packages = self.getSelectedJobPackages()
        self._selectAvailablePackages(job_packages)

    def getJobPackages(self):
        '''
        Return the package dictionaries for ALL QTreeItems
        '''
        job_packages = []
        for item in pyside_utils.get_top_level_items(self.ui_job_software_trwgt):
            job_packages.append(self.get_package_by_id(item.package_id))
        return job_packages

    def getSelectedJobPackages(self):
        '''
        Return the package dictionaries for each QTreeItem that is selected by
        the user.
        '''
        select_job_packages = []
        for item in self.ui_job_software_trwgt.selectedItems():
            select_job_packages.append(self.get_package_by_id(item.package_id))
        return select_job_packages

    def createJobPackageTreeWidgetItem(self, package):
        '''
        For the given software package, create a QTreeWidgetItem for it.
        with
        a text/name that describes it
        '''

        # This will be used for the "Software Name" column
        item_package_str = self._constructJobPackageStr(package)
        tree_item = QtWidgets.QTreeWidgetItem([item_package_str])
        tree_item.package_id = package["package_id"]
        return tree_item

    @staticmethod
    def _constructJobPackageStr(package):
        software_name = package["product"]

        # Construct the text to give the "Version" column. concatenate all version tiers together
        software_version = ".".join(filter(None, [package.get(v) for v in
                                                  ["major_version",
                                                   "minor_version",
                                                   "release_version",
                                                   "build_version"]]))
        return software_name + " " + software_version

    def validateJobPackages(self):
        '''
        Validate that all packages that have been added to the job are...valid.
        Return True if so, otherwise launch a dialog box to the user.
        '''
        job_packages = self.getJobPackages()
        job_package_ids = [p["package_id"] for p in job_packages]

        # LOOK FOR DUPLICATE PACKAGES ###
        duplicate_ids = set([x for x in job_package_ids if job_package_ids.count(x) > 1])
        duplicate_packages = [self.get_package_by_id(package_id) for package_id in duplicate_ids]

        if duplicate_packages:
            title = "Duplicate software packages!"
            dupe_package_strs = sorted(["- %s" % self._constructJobPackageStr(p) for p in duplicate_packages])
            msg = ("Duplicate software packages have been specified for the Job!\n\n"
                   "Please go the \"Job Software\" tab and ensure that only one "
                   "of the following packages has been specified:\n   %s") % "\n   ".join(dupe_package_strs)
            pyside_utils.launch_error_box(title, msg, parent=self)
            self.ui_tabwgt.setCurrentIndex(self._job_software_tab_idx)
            return False

        # LOOK FOR MULTIPLE PRODUCT PACKAGES ###
        packages_by_product = DefaultDict(list)
        for package in job_packages:
            packages_by_product[package["product"]].append(package)
        duplicate_product_strs = []
        for product_packages in packages_by_product.values():
            if len(product_packages) > 1:
                s_ = "- %s  (%s)" % (product_packages[0]["product"], " vs ".join([self._constructJobPackageStr(p)
                                                                                  for p in product_packages]))
                duplicate_product_strs.append(s_)

        if duplicate_product_strs:
            title = "Multiple software packages for the same product!"
            msg = ("Multiple software packages of the same product have been specified for the Job!\n\n"
                   "Please go the \"Job Software\" tab and ensure that only one "
                   "package for the following products have been specified:\n   %s") % "\n   ".join(duplicate_product_strs)
            pyside_utils.launch_error_box(title, msg, parent=self)
            self.ui_tabwgt.setCurrentIndex(self._job_software_tab_idx)
            return False

        # LOOK FOR PRESENCE OF A HOST PACKAGE ###
        for package in self.getJobPackages():
            if package["product"] == self.product:
                break
            # HACK to accommodate the mismatch of product names between maya and
            # mayaio (specifically when override packages are specified in the config)
            # TODO:(LWS: OMG GET RID OF THIS ASAP!!!
            if package["product"] == "maya" and self.product == "maya-io":
                break
        else:
            host_info = self.getHostProductInfo()
            title = "No software package selected for %s!" % self.product
            msg = ("No %s software package have been specified for the Job!\n\n"
                   "Please go the \"Job Software\" tab and select a one (potentially %s") % (self.product, host_info["version"])
            pyside_utils.launch_error_box(title, msg, parent=self)
            self.ui_tabwgt.setCurrentIndex(self._job_software_tab_idx)
            return False

        return True


class SubmitterPrefs(pyside_utils.UiFilePrefs):

    '''
    A class for interfacing with User preferences for the submitter UI.
    This subclasses adds functionality that is specific to the Conductor submitter.

    Preference names:
        scoutframes_str # str. The frames that the user set for scout frames

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
    # PREFERENCE NAMES (these the names that are used/written to the preference file (non widget)
    PREF_SCOUTFRAMES_STR = "scoutframes_str"
    PREF_JOB_PACKAGES_IDS = "job_packages_ids"

    @common.ExceptionLogger("Failed to load Conductor user preferences. You may want to reset your preferences from the options menu")
    def loadSubmitterUserPrefs(self, source_filepath=None):
        '''
        Load both the global and file-specific (e.g.nuke/maya file) user
        preferences for the UI widgets. This will reinstate any values on the
        widgets that that were recorded on them from the last time.

        First load the global preferences, then load the file-specific prefs
        which will override and of the global prefs
        '''
        # Load the global prefs
        self.loadGlobalWidgetPrefs()

        # If a source filepath has been provided, load it's file-specific prefs.
        if source_filepath:
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
    def getJobPackagesIds(self, filepath):
        '''
        Return the user settings for:
            the frame/range to use for scout frames
        '''
        return self.getPref(self.PREF_JOB_PACKAGES_IDS, filepath=filepath)

    @common.ExceptionLogger("Failed to save Conductor user preferences. You may want to reset your preferences from the options menu")
    def setJobPackagesIds(self, filepath, value):
        '''
        Set the user settings for:
            the frame/range to use for scout frames
        '''
        return self.setPref(self.PREF_JOB_PACKAGES_IDS, value, filepath=filepath)


class InstanceOptionsWidget(QtWidgets.QWidget):
    '''
    A widget that presents the user with instance options/knobs for their job/task.

    --- Design concepts ---
    Because there is an overwhelming amount of instance types for a user to choose from, this ui
    presents a "chain" of comboboxes that "walks" the user through each of the desired instance
    attributes. When the user makes a selection in one of the comboboxes, the comboboxes further
    down the chain are dynamically populated with correlating data.
    In the end there is a single hidden combobox that is constantly updating to reflect the actual
    name of the instance type that is being selected.
                                                                           `instance type`
        +------------+        +------------+        +------------+          +----------+
        | Combobox 1 |  --->  | Combobox 2 |  --->  | Combobox n |   --->   | Combobox |  (hidden)
        +------------+        +------------+        +------------+          +----------+


    Each item in a combobox is populated with 3 pieces of data:
      - text: the text that is displayed to the user
      - dict: the mapping that should be used to popluate the next (in-the-chain) combobox with.
      - key:  the dictionary key (str) that this item represents in the mapping
     e.g.

        {
            # The text to display
            QtCore.Qt.DisplayRole: 'Nvidia T4 Tensor',

            # The mapping to populate the next combobox with (the gpu count combobox)
            self.ROLE_CHILD_DATA: {
                1: {
                    '16/60':  'n1-standard-16-t4-1',
                    '8/30':   'n1-standard-8-t4-1'},
                4: {
                    '64/240': 'n1-standard-64-t4-4',
                   },
            },

            # The key in the
            self.ROLE_KEY: 'T4 Tensor',

        }
    '''
    # A custom data role for storing a dictionary key on a combobox item.
    ROLE_KEY = QtCore.Qt.UserRole + 1
    # A custom data role for storing the contents of the next "child" combobox in the combobox chain
    ROLE_CHILD_DATA = QtCore.Qt.UserRole + 2

    # The .ui designer filepath
    _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'instance_options.ui')

    # Serves as state storage for the "previous" selection of the cores/memory combobox.  Used when
    # toggling between gpu vs non-gpu instance types.
    # Two entries are stored in the variable (dict):
    #    - the *index* of the cores/memory combobox for the last time the gpu checkbox was *OFF*
    #    - the *index* of the cores/memory combobox for the last time the gpu checkbox was *ON*
    #  e.g.
    #    {
    #        False: 4, # when the gpu checkbox was off (False), the last combobox index was 4
    #        True:  2, # when the gpu checkbox was on (True), the last combobox index (2)
    #    }
    _last_cores_memory_idx = {}

    def __init__(self, instance_configs, parent=None):
        '''
        Args
            instance_configs: a list of of instance type configs (dicts), as provided by the
                `/api/v1/instance-types` endpoint. see `setInstanceConfigs` method.
        '''
        super(InstanceOptionsWidget, self).__init__(parent=parent)
        QtCompat.loadUi(self._ui_filepath, self)

        # Initialize the ui with the provided instance configs list
        self.setInstanceConfigs(instance_configs)

        # create/setup widgets
        self.createUi()

        # populate data in widgets
        self.populateUi()

        # Set default options
        self.applyDefaultSettings()

    def setInstanceConfigs(self, instance_configs):
        '''
        Initialize the ui with the given instance configs.  Generate lookup mappings that the ui
        comboboxes will rely upon in order to dynanically update content when another combobox
        changes.

        Args:
            instance_configs: list of instance configs (dicts) to populate the ui with, e.g.

                [
                    {
                        "cores": 160,
                        "memory": "3844",
                        "description": "160 core, 3844GB Mem",
                        "name": "n1-ultramem-160",
                        "gpu": null
                    },

                    {
                        "cores": 4,
                        "memory": "15",
                        "description": "4 core, 15GB Mem (1 T4 Tensor GPU with 16GB Mem)",
                        "name": "n1-standard-4-t4-1",
                        "gpu": {
                            "gpu_architecture": "NVIDIA Turing",
                            "total_gpu_cuda_cores": 2560,
                            "total_gpu_memory": "16",
                            "gpu_model": "T4 Tensor",
                            "gpu_cuda_cores": 2560,
                            "gpu_memory": "16",
                            "gpu_count": 1
                        }
                ]

        '''

        # store the instance_configs as-is for later usage
        self._instance_configs = instance_configs

        # create lookup map to find an instance config  by its instance type/name
        self._instance_configs_by_type = dict([(i["name"], i) for i in self._instance_configs])

        # generate data mappings for dynamic combobox content.
        self._combobox_map = self._generateComboboxMap()

        # generate a gpu lookup dictionary so that a gpu config can be found by providing the gpu model and gpu count.
        self._gpu_map = self._generateGpuMap()

    def createUi(self):
        '''
        Create/adjust widgets, make connections, etc
        '''

        # Connect slots/signals for dynamical combobox population/updates
        self.ui_gpu_chkbx.toggled.connect(self._gpuCheckboxToggled)
        self.ui_instance_type_cmbx.currentIndexChanged.connect(self._instanceTypeChanged)
        self.ui_gpu_model_cmbx.currentIndexChanged.connect(self._gpuModelChanged)
        self.ui_gpu_count_cmbx.currentIndexChanged.connect(self._gpuCountChanged)
        self.ui_cores_memory_cmbx.currentIndexChanged.connect(self._coresMemoryChanged)

        # connect the preemptible checkbox to enable/disable auto-retry widget
        self.ui_preemptible_chkbx.toggled.connect(self.ui_autoretry_wgt.setEnabled)

        # Hide the the instance-type widget.  We can potentially expose it in the future for
        # advanced users.
        self.ui_instance_type_wgt.hide()

    def populateUi(self):
        '''
        Populate the instance options comboboxes with available instance types.
        '''
        self.populateInstanceTypeCmbx(self._instance_configs, block_signals=True)

        # collect all gpu models that are available
        gpu_models = [model for model in self._combobox_map.keys() if model]

        # Hide/show the gpu widget, depending on whether any gpu instance types are available
        self.ui_gpu_wgt.setVisible(bool(gpu_models))

        # If there are any gpu instances, populate the gpu model/count comboboxes
        if gpu_models:
            self.populateGpuModelCmbx(self._combobox_map)
            current_model = self.ui_gpu_model_cmbx.currentData(role=self.ROLE_KEY)
            self.populateGpuCountCmbx(self._combobox_map[current_model])

        # trigger first item
        self.ui_instance_type_cmbx.currentIndexChanged.emit(self.ui_instance_type_cmbx.currentIndex())

    def applyDefaultSettings(self):
        '''
        Set the UI to default settings.
        '''

        # Set the default preemptible pref
        default_preemptible = CONFIG.get('preemptible')
        if default_preemptible is not None:
            self.setPreemptibleCheckbox(default_preemptible)

        # Set the default autoretry pref
        default_preempted_autoretry_count = CONFIG.get('autoretry_policy', {}).get("preempted", {}).get("max_retries")
        if default_preempted_autoretry_count is not None:
            self.setAutoretryCount(default_preempted_autoretry_count)

        # Set the default instance type to one specified in user config
        instance_type = CONFIG.get("instance_type")
        if instance_type:
            self.setInstanceType(instance_type)

    def _generateComboboxMap(self):
        '''
        Generate a tree of nested dicts that provide the content for dynamic combobox population.
        When one combobox is changed, the new item contains the data for the next "child" combobox.

        chain order:
            gpu_model --> gpu_count --> cores/memory --> instance-type

        Note that ideally the cores/memory value would have been stored as a two-item tuple e.g.
        (1, "1.3"), but PySide does not support combobox searching (QCombobox.findData()) for tuple
        types. This is a limitation of the python bindings to c++ objects.  See https://stackoverflow.com/a/63217982
        As a workaround, we concatenate the two values into a single string (separated by a slash),
        e.g "1/1.3". 

        Example tree:

            {
                # instance_configs that don't have a GPU
                None:
                    {0: {'1/3.8':    'n1-standard-1',
                         '160/3844': 'n1-ultramem-160',
                         '2/13':     'n1-highmem-2',
                         '2/7.5':    'n1-standard-2',
                         '96/360':   'n1-standard-96',
                         '96/86.4':  'n1-highcpu-96'},
                    },

                # instance_configs that have a T4 GPU
                'T4 Tensor':
                    {1: {'16/60':  'n1-standard-16-t4-1',
                         '8/30':   'n1-standard-8-t4-1'},
                     2: {'32/120': 'n1-standard-32-t4-2'},
                     4: {'64/240': 'n1-standard-64-t4-4'},
                    },

                # instance_configs that have a V100 GPU
                'V100':
                    {1: {'16/60':  'n1-standard-16-v100-1',
                         '4/15':   'n1-standard-4-v100-1',
                     2: {'24/120': 'n1-standard-24-v100-2'},
                     4: {'24/240': 'n1-standard-24-v100-4',
                         '48/312': 'n1-standard-48-v100-4'},
                     8: {'64/240': 'n1-standard-64-v100-8',
                         '96/624': 'n1-standard-96-v100-8'},
                    }
             }

        '''

        # Create the instance map by using nested DefaultDicts
        instance_map = DefaultDict(lambda: DefaultDict(lambda: DefaultDict(dict)))

        # cycle through each instance config to populate the map
        for instance_config in self._instance_configs:
            gpu_model, gpu_count, cores_memory = self._derive_lookup_keys(instance_config)
            instance_map[gpu_model][gpu_count][cores_memory] = instance_config["name"]

        return convert_default_dict(instance_map)

    def _derive_lookup_keys(self, instance_config):
        '''
        Derive the three combobox keys that are used for looking up the given instance config.
        The three keys are the:
            - gpu model
            - gpu count
            - cores/memory
        e.g.
            # the keys that map to the `n1-standard-1` instance type
            (None, 0, '1/3.8')

            # the keys that map to the `n1-standard-24-v100-4` instance type
            (T4 Tensor, 4, '24/240')

        Return: three-item tuple.
        '''
        gpu = instance_config.get("gpu") or {"gpu_model": None, "gpu_count": 0}
        cores_memory = "%s/%s" % (instance_config["cores"], instance_config["memory"])
        return gpu["gpu_model"], gpu["gpu_count"], cores_memory

    def _generateGpuMap(self):
        '''
        Generate a mapping that allows for a gpu (dict) to be found via gpu model/count.

        Key order:
            gpu_model --> gpu_count --> gpu dict


        {
            'T4':
                {1: {'gpu_architecture': 'NVIDIA Turing',
                    'gpu_count': 1,
                    'gpu_cuda_cores': 2560,
                    'gpu_memory': '16',
                    'gpu_model': 'T4 Tensor',
                    'total_gpu_cuda_cores': 2560,
                    'total_gpu_memory': '16'},
                2: {'gpu_architecture': 'NVIDIA Turing',
                    'gpu_count': 2,
                    'gpu_cuda_cores': 2560,
                    'gpu_memory': '16',
                    'gpu_model': 'T4 Tensor',
                    'total_gpu_cuda_cores': 5120,
                    'total_gpu_memory': '32'},
                },

             'V100':
                 {1: {'gpu_architecture': 'NVIDIA Volta',
                      'gpu_count': 1,
                      'gpu_cuda_cores': 5120,
                      'gpu_memory': '16',
                      'gpu_model': 'V100',
                      'total_gpu_cuda_cores': 5120,
                      'total_gpu_memory': '16'},
                  8: {'gpu_architecture': 'NVIDIA Volta',
                      'gpu_count': 8,
                      'gpu_cuda_cores': 5120,
                      'gpu_memory': '16',
                      'gpu_model': 'V100',
                      'total_gpu_cuda_cores': 4096,
                      'total_gpu_memory': u'128'},
                },
        }
        '''

        # Create the instance map by using a nesting of DefaultDicts
        gpu_map = {}

        # cycle through each instance to populate the map
        for instance_config in self._instance_configs:
            gpu = instance_config.get("gpu")
            if gpu:
                gpu_map[gpu["gpu_model"]] = gpu
        return gpu_map

    # -----------------------------------
    # Instance Type
    # -----------------------------------
    def getInstanceType(self):
        '''
        Return the active instance type from the ui (which may be hidden).
        '''
        return self.ui_instance_type_cmbx.currentData(role=self.ROLE_KEY)

    def setInstanceType(self, instance_type, block_signals=True):
        '''
        Set the UI's active instance-type combobox to the given instance type
        '''
        self._setActiveComboboxItem(
            self.ui_instance_type_cmbx,
            instance_type,
            self.ROLE_KEY,
            block_signals=block_signals,
        )

    def populateInstanceTypeCmbx(self, instances, block_signals=True):
        '''
        Populate the instance-type combobox with the given list of instances (dicts)
        '''
        items = []
        # sort instances by gpu, then by # of cores, then by amount of memory.
        for instance in sorted(instances, key=operator.itemgetter("gpu", "cores", "memory")):
            items.append({
                QtCore.Qt.DisplayRole: instance["name"],
                self.ROLE_KEY: instance["name"],
                self.ROLE_CHILD_DATA: instance,
            })
        pyside_utils.populate_combobox(self.ui_instance_type_cmbx, items, block_signals=block_signals)

    def _instanceTypeChanged(self, index):
        '''
        When the instance type changes, it must update *all* comboboxes to reflect the attributes
        of the the newly selected instance type.

        1. check/uncheck the GPU checkbox
        2. populate GPU Model combox entries
        3. set active GPU Model (block signals)
        4. populate GPU Count combox
        5. set active GPU Count (block signals)
        6. populate cores/memory comoboox
        7. set active cores/memory (block signals)
        '''

        # Fetch the instance info (dict) for the newly selected/active instance type
        instance_config = self.ui_instance_type_cmbx.itemData(index, role=self.ROLE_CHILD_DATA)

        gpu_model, gpu_count, cores_memory = self._derive_lookup_keys(instance_config)

        # enable/disable the gpu checkbox (based upon whether the instance_config has a gpu
        self.ui_gpu_chkbx.setChecked(bool(gpu_model))

        # If the instance config has a gpu, then populate the ui comboboxes to reflect the gpu info
        if gpu_model:
            self.setGpuModel(gpu_model)
            self.populateGpuCountCmbx(self._combobox_map[gpu_model])
            self.setGpuCount(gpu_count)

        # Populate the cores/memory combobox
        self.populateCoresMemoryCmbx(self._combobox_map[gpu_model][gpu_count])

        # Set the active cores/memory entry to reflect the same value as the instance_config.
        self.setCoresMemory(cores_memory)

    def _gpuCheckboxToggled(self, checked):
        '''
        When the gpu checkbox changes...
          1. Enable/disable the gpu widget (reflect the gpu checkbox)
          2. Populate the cores/memory combobox (reflect whether gpus should be included or not)
          3. Restore the last cores/memory selection from the prior gpu checked/unchecked state. 
        '''
        self.ui_gpu_type_wgt.setEnabled(checked)
        # If the gpu checkbox is checked on then populate the memory/cores combobox with gpu instances.
        if checked:
            mapping = self.ui_gpu_count_cmbx.currentData(role=self.ROLE_CHILD_DATA)
            self.populateCoresMemoryCmbx(mapping)
        # otherise populate the memory/cores combobox with non-gpu instances
        else:
            self.populateCoresMemoryCmbx(self._combobox_map[None][0])

        # Attempt to find the the old combobox entry. If there isn't one, default to the first index.
        index = self._last_cores_memory_idx.get(checked, 0)

        # Set the current combobox item (restore the state). This will will trigger a cascading ui update.
        self.ui_cores_memory_cmbx.setCurrentIndex(index)

    # -----------------------------------
    # GPU MODEL
    # -----------------------------------

    def setGpuModel(self, gpu_model, block_signals=True):
        '''
        Set the gpu model combobox's active item to that of the the given `gpu_model` (the KEY value).
        '''
        self._setActiveComboboxItem(
            self.ui_gpu_model_cmbx,
            gpu_model,
            self.ROLE_KEY,
            block_signals=block_signals,
        )

    def populateGpuModelCmbx(self, data, block_signals=True):
        '''
        Populate the Gpu Model combobox with the given data.
        '''
        # Populate Gpus dropdown
        items = []
        for gpu_model, gpu_count_mapping in data.iteritems():
            if gpu_model:
                gpu = self._gpu_map[gpu_model]
                tooltip = "{gpu_architecture} {gpu_model} GPU with {gpu_cuda_cores} Cuda cores and {gpu_memory}GB memory"
                items.append({
                    # TODO(lws): Remove hard-coded "nvidia". The vendor name should be provided via backend
                    QtCore.Qt.DisplayRole: "Nvidia %s" % gpu_model,
                    QtCore.Qt.ToolTipRole: tooltip.format(**gpu),
                    self.ROLE_KEY: gpu_model,
                    self.ROLE_CHILD_DATA: gpu_count_mapping,
                })

        pyside_utils.populate_combobox(self.ui_gpu_model_cmbx, items, block_signals=block_signals)

    def _gpuModelChanged(self, index):
        instance_map = self.ui_gpu_model_cmbx.itemData(index, role=self.ROLE_CHILD_DATA)
        self.populateGpuCountCmbx(instance_map)
        self.ui_gpu_count_cmbx.currentIndexChanged.emit(self.ui_gpu_count_cmbx.currentIndex())

    # -----------------------------------
    # GPU COUNT
    # -----------------------------------

    def setGpuCount(self, gpu_count, block_signals=True):
        '''
        Set the active Gpu Count entry to that of the given gpu_count.
        '''
        self._setActiveComboboxItem(
            self.ui_gpu_count_cmbx,
            gpu_count,
            self.ROLE_KEY,
            block_signals=block_signals,
        )

    def populateGpuCountCmbx(self, data, block_signals=True):
        '''
        Populate Gpu Count combobox with the given data.
        '''
        items = []
        for gpu_count, instance_map in sorted(data.iteritems()):
            # skip any entries that don't have a gpu_count (i.e. don't include gpus)
            if gpu_count:
                items.append({
                    QtCore.Qt.DisplayRole: str(gpu_count).rjust(1),  # use rjust to  vertically align numeric placeholders
                    self.ROLE_CHILD_DATA: instance_map,
                    self.ROLE_KEY: gpu_count,
                })

        pyside_utils.populate_combobox(self.ui_gpu_count_cmbx, items, block_signals=block_signals)

    def _gpuCountChanged(self, index):
        '''
        When the gpu count changes, fetch the data for the downstream combobox (cores/memory),
        and populate it.
        '''
        mapping = self.ui_gpu_count_cmbx.itemData(index, role=self.ROLE_CHILD_DATA)
        self.populateCoresMemoryCmbx(mapping)
        # Artificially trigger that the index changed (just  use the current index)
        self.ui_cores_memory_cmbx.currentIndexChanged.emit(self.ui_cores_memory_cmbx.currentIndex())

    # -----------------------------------
    # CORES/MEMORY
    # -----------------------------------
    def setCoresMemory(self, cores_memory, block_signals=True):
        '''
        Set the active Cores/Memory entry to that of the given cores_memory value.
        '''
        self._setActiveComboboxItem(
            self.ui_cores_memory_cmbx,
            cores_memory,
            role=self.ROLE_KEY,
            block_signals=block_signals,
        )

    def populateCoresMemoryCmbx(self, data, block_signals=True):
        '''
        Populate the cores/memory combobox using the given data.  Sort the entries by number of 
        cores, then by memory.
        '''
        def _sort_by_cores_and_memory(item):
            instance_config = self._instance_configs_by_type[item[1]]
            return (instance_config["cores"], float(instance_config["memory"]))

        items = []
        for cores_memory, instance_type in sorted(data.iteritems(), key=_sort_by_cores_and_memory):
            instance_config = self._instance_configs_by_type[instance_type]
            items.append({
                self.ROLE_CHILD_DATA: instance_type,
                QtCore.Qt.DisplayRole: '{cores} core, {memory}GB memory'.format(**instance_config),
                self.ROLE_KEY: cores_memory,
            })

        pyside_utils.populate_combobox(self.ui_cores_memory_cmbx, items, block_signals=block_signals)

    def _coresMemoryChanged(self, index):
        '''
        When the cores/memory combobox changes...
          1. fetch the instance type from the newly selected item.
          2. Set the instance-type combobox to that instance type (the combobox may be hidden).
          3. Save this new state so that we can restore it later (i.e. when toggling the gpu checkbox)
        '''
        # get the instance type from the current item in the combobox
        instance_type = self.ui_cores_memory_cmbx.itemData(index, role=self.ROLE_CHILD_DATA)
        # Set the instance type combobox to this instance type
        self.setInstanceType(instance_type, block_signals=True)
        # Save the cores/memory index so that we can restore it later (when gpu checkbox is toggled)
        self._last_cores_memory_idx[self.ui_gpu_chkbx.isChecked()] = index

    def getPreemptibleCheckbox(self):
        '''
        Return whether or not the "Preemptible" checkbox is checked.
        '''
        return self.ui_preemptible_chkbx.isChecked()

    def setPreemptibleCheckbox(self, is_checked):
        '''
        Set the checkbox value for the "Preemptible" checkbox
        '''
        return self.ui_preemptible_chkbx.setChecked(is_checked)

    def setAutoretryCount(self, count):
        '''
        Set the UI's Auto Retry spinbox value
        '''
        self.ui_autoretry_spnbx.setValue(int(count))

    def getAutoretryCount(self):
        '''
        Get the UI's Auto Retry spinbox value
        '''
        return self.ui_autoretry_spnbx.value()

    def getAutoretryPolicy(self):
        '''
        Construct/return an autoretry policy if the user as selected to use preemptible instances.
        '''
        # Only return an autoretry policy if the user has specified preemptible instances
        if self.getPreemptibleCheckbox():
            max_retries = self.getAutoretryCount()
            return {"preempted": {"max_retries": max_retries}}

    @common.ExceptionLogger("Failed to save Conductor user preferences. You may want to reset your preferences from the options menu")
    def savePreemptiblePref(self, is_checked):
        '''
        Save the "Preemptible" checkbox user preference for the open file
        '''
        filepath = self.getSourceFilepath()
        widget_name = self.sender().objectName()
        return self.prefs.setFileWidgetPref(filepath, widget_name, bool(is_checked))

    @classmethod
    def _setActiveComboboxItem(cls, combobox, data, role, block_signals=True):
        '''
        For the given combobox, set the active item to the one that matches the given data for the
        given data role.  If no item in the combobox matches, raise an exception.

        Args:
            combobox: QCombobox object.
            data: data that must be found on the combobox entry in order to identify it as the item
                to set active.
            role: the data role that the given data is used for.
                see: https://doc.qt.io/qtforpython/PySide2/QtCore/Qt.html#PySide2.QtCore.PySide2.QtCore.Qt.ItemDataRole
        '''
        idx = combobox.findData(data, role)
        if idx == -1:
            raise Exception('cannot find data in combobox "%s": %s' % (combobox.objectName(), data))
        combobox.blockSignals(block_signals)
        combobox.setCurrentIndex(idx)
        combobox.blockSignals(False)


class TaskFramesGenerator(object):
    '''
    This base class provides functionality to Job's command to be suitable
    for execution for a single Task. The general idea is that the submitted job
    command has subsitutable characters (args) that should be populated
    differently for each task (e.g. so that each task renders different frames, etc).

    Because every rendering software has it's own rendering command with differing
    arguments/syntax, this class is intendeded to be subclassed for each product.

    Specific problems that this class addresses:

        1. Converting a job's "frame_range" argument into individual frames so
           that each task is allocated unique frame(s) to render.

        2. Reading and applying those frames to the Task's render command
           arguments. The render command syntax may be different for each product.

        3. Taking into consideration the job's "chunk_size" argument so that
           a single Task can work on multiple frames.  This also includes interpreting
           any "steps" that have been indicated in the job's "frame_range" argument.

    Note that this class is an iterator so that it can be iterated upon until
    a command for each task has been dispensed. It provides two items upon each
    iteration:
        - A command that has been fully resolved for a task
        - a list of frames (ints) that the task will be rendering

    Example usage (using MayaTaskCommand child class):
        # Instantiate the class with proper args
        >>> cmd_generator = base_utils.MayaTaskCommand(command="Render <frame_args> deadpool.ma",
        ...                                            frame_range ="1-10x2",
        ...                                            frame_padding = 4,
        ...                                            chunk_size= 2)

        # Iterate over the class object, dispensing command and frame data for each task
        >>> for command, frames in cmd_generator:
        ...     print "command:", command
        ...     print "frames:", frames
        ...
        command: Render -s 1 -e 3 -b 2 deadpool.ma
        frames: (1, 3)
        command: Render -s 5 -e 7 -b 2 deadpool.ma
        frames: (5, 7)
        command: Render -s 9 -e 9 -b 1 deadpool.ma
        frames: (9,)

     '''
    task_frames = None

    def __init__(self, frames, chunk_size=1, uniform_chunk_step=True):
        '''
        frames: list or integers (frame numbers) to render for the job
        chunk_size: int. the "chunk_size" arg that was submitted for the job
        # Dictates whether a chunk of frames must have the same step between them
        '''
        self._chunk_size = chunk_size

        # copy the original frame list. This will track which frames have not been dispensed yet
        self._undispensed_frames = list(frames)
        self._uniform_chunk_step = uniform_chunk_step

    def __iter__(self):
        return self

    def next(self):
        '''
        Everytime the object is iterated on, return a tuple that contains two
        items:
            - a new command (str) that is appropriate to be executed by a task.
              (unique from the prior ones)
            - a list of corresponding frames (ints) that the command will render

            start_frame, end_frame, step, task_frames
        '''
        # Generate w new task command (from the outstanding/undispensed frames
        # to be allocated)
        next_task_frames = self._next(self._chunk_size, self._uniform_chunk_step)
        if next_task_frames:
            # Return the command for the task, and the accompanying frames list.
            return next_task_frames

        # If there isn't a command, then it means all frames have been allocated
        # to task commands
        raise StopIteration

    def _next(self, chunk_size, uniform_chunk_step):
        '''
        Construct and return the command to be executed for a task. This command
        is specific per product.  The returned command should be fully resolved
        and ready to be executed by the task. In other words, resolve all arguments for
        the command, such as the frames(s) to be rendered (taking into consideration
        steps and chunks, etc).

        Call this method repeatedly to dispense a new task command (until all
        frames have been dispensed/allocated).
        '''

        # Get the list of frames that is appriate for the chunk size
        task_frames = self.get_next_frames_chunk(chunk_size, uniform_chunk_step)
        logger.debug("task_frames: %s", task_frames)

        if task_frames:

            # Get the first frame from the chunk
            start_frame = str(task_frames[0])
            logger.debug("start_frame: %s", start_frame)

            # Get the last frame from the chunk
            end_frame = str(task_frames[-1])
            logger.debug("end_frame: %s", end_frame)

            steps = self.derive_steps(task_frames)
            logger.debug("steps: %s", steps)

            # Validate that the there is only 1 step between the frames in the chunk
            assert len(steps) == 1, "More than one step in frames chunk. Frames chunk: %s.  Steps found: %s" % (task_frames, steps)

            step = str(steps[0])
            logger.debug("step: %s", step)

            return start_frame, end_frame, step, task_frames

    def get_next_frames_chunk(self, chunk_size, uniform_chunk_step=True):
        '''
        Return then "next" chunk of frames (that the task will render). This
        may be a list of one frame or several.

        e.g. [1] # single frame
             [1, 2 ,3]  # multiple frames
             [1,2,3,40,100,101] # multiple frames (No common step. This can be problematic depending on the render command)

        uniform_chunk_step: bool. If True, will only return a chunk of frames
                            that have a uniform step size between them.


        more complicated example:
            frame_range = "1-5x2,20-25,10-30x5,200,1000"
            chunk_size = 4
            step_size=5

            resulting task frames:
                task 0: [1]
                task 1: [3]
                task 2: [5, 10, 15, 20]  # range conforms to step size (5)
                task 3: [21]
                task 4: [22]
                task 5: [23]
                task 6: [24]
                task 7: [25,30] # range conforms to step size (5)
                task 8: [200]
                task 9: [1000]

        '''
        task_frames = ()

        # Cycle through each potential frame in the chunk size
        for _ in range(chunk_size):

            # If all frames have been dispensed, return the chuck (which could be empty)
            if not self._undispensed_frames:
                # logger.debug("all frames dispensed")
                return task_frames

            next_frame = self._undispensed_frames[0]
            # Add the frame to the chunk if we don't care what the step size is
            # Or the frame is the only frame in the chunk (so far)...
            # Or if the frame follows the same step as the rest of the chunk frames (it's uniform)
            if not uniform_chunk_step or not task_frames or len(set(self.derive_steps(task_frames + (next_frame,)))) == 1:
                task_frames += (next_frame,)

                # Pop a frame off the undispensed listnext_frames_chunk
                self._undispensed_frames.pop(0)

            # Otherwise break the loop (and return whatever the chunk is at this point)
            else:
                break

        return task_frames

    @classmethod
    def derive_steps(cls, frames):
        '''
        Inspect the list of frames and derive what the "step" is between them. If
        more than one step is found, return the lowest and highest steps

        e.g.
             FRAMES                    STEPS
             -------------------------------------------------
             [1,2,3,4]         ->      [1]      # one step count between frames (1)
             [-1,-3,-5,-7]     ->      [2]      # one step count between frames (2)
             [1,3,5,17]        ->      [2, 12]  # multiple step counts between frames (2, 12)
             [4]               ->      [1]      # if there isn't an actual step count, default to 1

        The main functionality taken from: http://stackoverflow.com/questions/3428769/finding-the-largest-delta-between-two-integers-in-a-list-in-python
        '''
        # make a copy of the frames list, and then sort it (it should be sorted already, but just to be sure)
        frames = sorted(list(frames))

        # Get the steps between each frame
        steps = [abs(x - y) for (x, y) in zip(frames[1:], frames[:-1])]

        # deduplicate steps from list
        return sorted(set(steps)) or [1]

    @classmethod
    def get_padded_frame(cls, frame_int, padding_int):
        '''
        Return the given (frame) number as string with the given padding
        applied to it
        '''
        padded_str = "%%0%sd" % padding_int
        return padded_str % frame_int

    @classmethod
    def group_contiguous_frames(cls, frames, ends_only=False):
        '''
        Separate the given list of frames into groups(sublists) of contiguous frames/

        e.g. [1,2,3,15,16,17,21,85] --> [(1,2,3),(15,16,17), (21), (85)]

        if ends_only==True, return only first and last frames of each group (i.e. "bookends only")
            e.g. [(1,3),(15,17), (21), (85)]

        taken from: http://stackoverflow.com/questions/2154249/identify-groups-of-continuous-numbers-in-a-list
        '''
        ranges = []
        for _, group in groupby(enumerate(frames), lambda index_item: index_item[0] - index_item[1]):
            group_ = map(operator.itemgetter(1), group)
            if ends_only:
                ranges.append((group_[0], group_[-1]))
            else:
                ranges.append(tuple(group_))
        return ranges


def convert_default_dict(default_dict):
    '''
    Convert the given DefaultDict object into a standard dictionary, recursively doing the same
    for any DefaultDicts found within.

    '''
    for key, item in default_dict.items():
        if isinstance(item, DefaultDict):
            default_dict[key] = convert_default_dict(item)
        else:
            default_dict[key] = item

    return dict(default_dict)


if __name__ == "__main__":
    '''
    Run the ui as a standalone application
    '''
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    ui = ConductorSubmitter.runUi()
    sys.exit(app.exec_())
