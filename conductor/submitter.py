import collections
from pprint import pformat
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
from conductor import submitter_resources  # This is a required import  so that when the .ui file is loaded, any resources that it uses from the qrc resource file will be found
from conductor.lib import  conductor_submit, pyside_utils, common, api_client, loggeria, package_utils

PACKAGE_DIRPATH = os.path.dirname(__file__)
RESOURCES_DIRPATH = os.path.join(PACKAGE_DIRPATH, "resources")

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

        # Setup the top menu bar
        self.setupMenuBar()

        # Set the radio button on for the start/end frames by default
        self.on_ui_start_end_rdbtn_toggled(True)

        # Populate the Instance Type combobox with the available instance configs
        self.populateInstanceTypeCmbx()

        # Populate the software versions tree widget
        self.populateSoftwareVersionsTrWgt()

        self.filterPackages(show_all_versions=self.ui_show_all_versions_chkbx.isChecked())

        self.autoDetectSoftware()

        # Populate the Project combobox with customer's projects
        self.populateProjectCmbx()

        # Set the default instance type
        self.setInstanceType(self.default_instance_type)

        # Hide the widget that holds advanced settings. TODO: need to come back to this.
        self.ui_advanced_wgt.hide()

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

        # Add the extended widget (must be implemented by the child class
        self._addExtendedWidget()

        # shrink UI to be as small as can be
        self.adjustSize()

        # Set the keyboard focus on the frame range radio button
        self.ui_start_end_rdbtn.setFocus()


        # Check for resource in config, if available disable lineedit and set value
        if CONFIG.get('resource'):
            self.ui_resource_lnedt.setEnabled(False)
            self.setResource(CONFIG.get('resource'))


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
        self.addLoggingMenu(self.ui_set_log_level_qmenu)


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

    def setProject(self, project_str):
        '''
        Set the UI's Project field
        '''
        index = self.ui_project_cmbx.findText(project_str)
        if index == -1:
            raise Exception("Project combobox entry does not exist: %s" % project_str)

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
        conductor_args["software_package_ids"] = self.getSoftwarePackageIds()
        return conductor_args

    def getCommand(self):
        '''
        Return the command string that Conductor will execute
        '''
        class_method = "%s.%s" % (self.__class__.__name__, inspect.currentframe().f_code.co_name)
        message = "%s not implemented. Please override method as desribed in its docstring" % class_method
        raise NotImplementedError(message)

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
        if response_code in [201, 204]:
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
        if not self.validateJobPackages():
            return

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


    @QtCore.Slot(name="on_ui_choose_output_path_pbtn_clicked")
    def on_ui_choose_output_path_pbtn_clicked(self):

        dirpath = str(QtGui.QFileDialog.getExistingDirectory(self, "Select Directory"))
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
        Validate that the given frame range text conforms to the expected format via regexing
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


    def getUserSettingWidgets(self):
        '''
        Return a list of widget objects that are appropriate for restoring their
        state (values) from a user's preference file. These widgets are identified 
        by a dynamic property that has been set on them via Qt Designer.
        The property name is "isUserSetting" and it's a bool which should be 
        set to True.
        '''
        user_setting_identifier = "isUserSetting"
        return pyside_utils.get_widgets_by_property(self,
                                                    user_setting_identifier,
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
        Read any user preferences that may have been stored for the currently 
        opened source file (maya/katana/nuke file, etc) and apply those values
        to the widgets. These widgets are identified 
        by a dynamic property that has been set on them via Qt Designer.
        The property name is "isUserSetting" and it's a bool which should be 
        set to True.
        '''
        try:
            source_filepath = self.getSourceFilepath()
            usersetting_widgets = self.getUserSettingWidgets()
            pyside_utils.UiUserSettings.loadUserSettings(company_name=self.company_name,
                                                         application_name=self.__class__.__name__,
                                                         group_name=source_filepath,
                                                         widgets=usersetting_widgets)
        except:
            settings_filepath = pyside_utils.UiUserSettings.getSettingsFilepath(self.company_name,
                                                                                self.__class__.__name__)
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
            usersetting_widgets = self.getUserSettingWidgets()
            pyside_utils.UiUserSettings.saveUserSettings(company_name=self.company_name,
                                                         application_name=self.__class__.__name__,
                                                         group_name=source_filepath,
                                                         widgets=usersetting_widgets)
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



    ###########################################################################
    #  SOFTWARE PACKAGES
    ###########################################################################


    def getHostProductInfo(self):
        raise NotImplementedError


    def getPluginsProductInfo(self):
        return []

    def introspectSoftwareInfo(self):
        host_product_info = self.getHostProductInfo()
        assert host_product_info, "No host product info retrieved"
        plugin_products_info = self.getPluginsProductInfo()
        return [host_product_info] + plugin_products_info

    def autoDetectSoftware(self):
        '''
        Of the given packages, return the packages that match

        1. host software
        2. plugins
            - renderer
            - others
        '''

        self.ui_job_software_trwgt.clear()
        tree_packages = self.getTreeItemPackages().values()

        softwares_info = self.introspectSoftwareInfo()



        matched_packages = []
        unmatched_software = []
        for software_info in softwares_info:
#             package_item = self.getBestPackage(software_info, tree_packages)
            package_id = software_info.get("package_id")
            package = self.software_packages.get(package_id)
            if not package:
                unmatched_software.append(software_info)
            else:
                matched_packages.append(package)


        self.populateJobSoftwareTrwgt(matched_packages)

        if unmatched_software:
            msg = "Could not match software info: \n\t%s" % ("\n\t".join([pformat(s) for s in unmatched_software]))
            logger.warning(msg)
            package_strs = ["- %s: %s %s" % (p["product"], p["version"], "(for %s: %s)" % (p["host_product"], p["host_version"]) if p.get("host_product") else "")
                            for p in unmatched_software]
            msg = "The following software packages could not be auto matched:\n  %s" % "\n  ".join(package_strs)
            msg += '\n\nManually add desired software packages in the "Job Software" tab'

            title = "Job Submission Failure"
            pyside_utils.launch_error_box(title, msg, parent=self)
            self.ui_tabwgt.setCurrentIndex(self._job_software_tab_idx)

    ###########################################################################
    ######################  AVAILABLE SOFTWARE TREEWIDGET  - self.ui_software_versions_trwgt
    ###########################################################################

    @QtCore.Slot(name="on_ui_add_to_job_pbtn_clicked")
    def on_ui_add_to_job_pbtn_clicked(self):
        self._availableAddSelectedItems()
        self.validateJobPackages()


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

        # Get packages that are host packages (i.e. not plugins). This is the "top" of the heirarchy
        host_packages = [package for package in self.software_packages.values() if not package["plugin_host_product"]]

        # These are the names of the top leve product groups .e.g. "maya", "nuke", "katana"
        top_level_product_items = {}

        # Create a tree item for every package (we'll group/parent them later)
        # TODO:(LWS) This really ought to be a more clever recursive function. This is currently hard coded for only two depth levels.
        for host_package in host_packages:

#             # # TOP LEVEL PRODUCT GROUP ##
#             product_name = host_package["product"]
#             product_group_item = top_level_product_items.get(product_name)
#             if not product_group_item:
#                 product_group_item = QtGui.QTreeWidgetItem([product_name, ""])
#                 product_group_item.product = product_name
#                 top_level_product_items[product_name] = product_group_item
#                 self.ui_software_versions_trwgt.addTopLevelItem(product_group_item)

            ## HOST PRODUCT PACKAGE ###
            host_package_item = self.createPackageTreeWidgetItem(host_package)
#             product_group_item.addChild(host_package_item)
            self.ui_software_versions_trwgt.addTopLevelItem(host_package_item)

            # # PLUGINS FOR PRODUCT ##
            plugin_parent_items = {}
            for plugin_id in host_package["plugins"]:
                plugin_package = self.software_packages.get(plugin_id)
                if not plugin_package:
                    logger.warning("Not able to find expected plugin. Id: %s", plugin_id)
                    continue

                ### PLUGIN PRODUCT GROUP ####
                plugin_product_name = plugin_package["product"]
                plugin_parent_product_item = plugin_parent_items.get(plugin_product_name)
                if not plugin_parent_product_item:
                    plugin_parent_product_item = QtGui.QTreeWidgetItem([plugin_product_name, ""])
                    plugin_parent_product_item.product = plugin_product_name
                    plugin_parent_items[plugin_product_name] = plugin_parent_product_item
                    host_package_item.addChild(plugin_parent_product_item)

                ### PLUGIN PRODUCT PACKAGE ###
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
        host_package_info = self.getHostProductInfo()
        host_package_id = host_package_info["package_id"]
        host_package = self.get_package_by_id(host_package_id) if host_package_id else None
        for host_package_item in self.getHostPackageTreeItems():
            self.ui_software_versions_trwgt.setItemHidden(host_package_item, True)
            package = self.get_package_by_id(host_package_item.package_id)
            if package["product"] == self.product:
                if show_all_versions or not host_package or package == host_package:
                    self.ui_software_versions_trwgt.setItemHidden(host_package_item, False)



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
#         maching_packages = self.getMatchingPackages(software_info, packages)
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
        matching_packages = self.getMatchingPackages(software_info, packages)
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

    def getMatchingPackages(self, software_info, packages):
        return package_utils.get_matching_packages(software_info, packages)



    def createPackageTreeWidgetItem(self, package):
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
        tree_item = QtGui.QTreeWidgetItem([software_name, software_version])
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
        return self.software_packages[package_id]


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
        menu = QtGui.QMenu()

        # "check selected" menu item
        action = menu.addAction("Add selected packages to Job", self._availableAddSelectedItems)
#         action = menu.addAction("remove selected",
#                                 lambda check=True: self._check_all_selected(check))
        return menu



    def _availableAddSelectedItems(self):
        for available_package in self.getSelectedAvailablePackages():
            job_package_item = self.createJobPackageTreeWidgetItem(available_package)
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
    ######################  JOB SOFTWARE TREEWIDGET  - self.ui_job_software_trwgt
    ###########################################################################

    @QtCore.Slot(name="on_ui_auto_detect_pbtn_clicked")
    def on_ui_auto_detect_pbtn_clicked(self):
        self.autoDetectSoftware()

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
        menu = QtGui.QMenu()

        # "check selected" menu item
        action = menu.addAction("Remove selected packages", self._jobRemoveSelectedItems)
#         action = menu.addAction("remove selected",
#                                 lambda check=True: self._check_all_selected(check))
        return menu

    def _jobRemoveSelectedItems(self):
        for item in self.ui_job_software_trwgt.selectedItems():
            index = self.ui_job_software_trwgt.indexOfTopLevelItem(item)
            self.ui_job_software_trwgt.takeTopLevelItem(index)

    def _jobFindSelectedItemsInAvailableTree(self):
        job_packages = self.getSelectedJobPackages()
        self._selectAvailablePackages(job_packages)


    def getJobPackages(self):
        '''
        Return the package dictionaries for each QTreeItem that is selected by
        the user.
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
        tree_item = QtGui.QTreeWidgetItem([item_package_str])
        tree_item.package_id = package["package_id"]
        return tree_item

    def _constructJobPackageStr(self, package):
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





        ### LOOK FOR DUPLICATE PACKAGES ###
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


        ### LOOK FOR MULTIPLE PRODUCT PACKAGES ###
        packages_by_product = collections.defaultdict(list)
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


        ### LOOK FOR PRESENCE OF A HOST PACKAGE ###
        for package in self.getJobPackages():
            if package["product"] == self.product:
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

if __name__ == "__main__":
    app = QtGui.QApplication.instance()
    if app is None:
        app = QtGui.QApplication(sys.argv)
    ConductorSubmitter.runUi()
