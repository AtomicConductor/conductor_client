import collections
from pprint import pformat
import imp
import logging
import os
import operator
import sys
import inspect
import functools
import time
import traceback
from PySide import QtGui, QtCore

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conductor import CONFIG
from conductor.lib import  conductor_submit, pyside_utils, common, api_client, loggeria, package_utils, file_utils
from conductor import submitter_resources  # This is a required import  so that when the .ui file is loaded, any resources that it uses from the qrc resource file will be found

PACKAGE_DIRPATH = os.path.dirname(__file__)
RESOURCES_DIRPATH = os.path.join(PACKAGE_DIRPATH, "resources")
SUCCESS_CODES_SUBMIT = [201, 204]

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
7. tool tips for all widget fields
9. what are the available commands for the "cmd" arg?

'''


class StepDecorator(object):

    def __init__(self, step_name=None):
        self.step_name = step_name

    def __call__(self, function):
        '''
        This gets called during python compile time (as all decorators do).
        It will always have only a single argument: the function this is being
        decorated.  It's responsbility is to return a callable, e.g. the actual
        decorator function
        '''
        @functools.wraps(function)
        def decorater_function(*args, **kwargs):
            '''
            The decorator function

            Tries to execute the decorated function. If an exception occurs,
            it is caught, takes the action, and then raises the exception.
            '''
            assert len(args) > 0, "Must at least have self as an argument"
            thread_instance = args[0]

            step_name = self.step_name or function.__name__
            thread_instance.sig_step_started.emit("Running: %s" % step_name)
            result = function(*args, **kwargs)
            thread_instance.sig_step_finished.emit("Finished: %s" % step_name)
            return result

        return decorater_function





class SubmissionThread(QtCore.QThread):
    '''
    This class is eparate thread that will be run apart from the
    main ui thread.  This allows the main ui to remain responsive and display
    updates/progress of what this thread is doing.
    
    Specifically, this class is handling the entire submission process (from
    the moment the user presses the "submit" button).  This submission processes
    can be broken down into several stages so that progress percentage and feedback
    can be provided to the user.  This thread also allows for the cancelling
    of the submission process by the user.
    
    These are the stages of the submission process:
        1. Argument Gathering
            - collectDependencies
                -depencying processing
        2. Argument Validation
        3. Job Submission
        4. Post submission processes
        5
        
    This thread will exit in the following circumstances:
        1. The user cancels the process
        2. An exception is raised 
        3. The process completes
        
    When the thread exits, it will provide the following information on it's object:
        - result:  This will only be available if no exceptions have been raised. 
                    This is simply the return data of the submission process
        - exception: This is the sys.exc_info() from any exception that occurs. Otherwise None.
        
        
    This thread communicates via signals:
        - sig_step_started:  The step has started
        - sig_step_finished: The step completed
        - sig_log: emits log information that might be useful for capturing (and displaying in the UI)
         
    
    This thread is really kinda hacky because it actually uses the main thread's
    gui object. This is required because the gui object has many methods and attributes
    that are required for this submission process, such as gathering arguments
    (from the gui), and querying other data stored in the gui.
    
    '''

    sig_step_started = QtCore.Signal(object)
    sig_step_finished = QtCore.Signal(object)
    sig_log = QtCore.Signal(object)

    result = None
    exception = None
    canceled = False
    steps = ["Presubmission",
             "Job Argument Gathering",
             "Job Argument Validation",
             "Job Submission"]
    _log = ""


    def __init__(self, ui):
        self.ui = ui
        super(SubmissionThread, self).__init__()

    def __del__(self):
        self.wait()

    def run(self):

        try:
            self.result = self.main()
        except:
            self.exception = sys.exc_info()

    def main(self):
        self.check_canceled()
        self.run_pre_submission()
        self.check_canceled()
        job_args = self.get_job_args()
        self.check_canceled()
        validated_args = self.validate_job_args(job_args)
        self.check_canceled()
        return self.submit_job(validated_args)

    @StepDecorator("Presubmission")
    def run_pre_submission(self):
        self.log("This is a presub message")
        data = self.ui.runPreSubmission()
        return data


    @StepDecorator("Job Argument Gathering")
    def get_job_args(self):
        self.log("This is a Argument Gathering message")
        job_args = self.ui.getJobArgs()
        time.sleep(1)
        return job_args

    @StepDecorator("Job Argument Validation")
    def validate_job_args(self, job_arguments):
        self.log("This is a Argument Validation message")
        validated_args = self.ui.validateJobArgs(job_arguments)
        time.sleep(1)
        return validated_args

#     @StepDecorator("Job Submission")
#     def submit_job(self, job_arguments):
#         submission = conductor_submit.Submit(job_arguments)
#         result = submission.main()
#         return result

    @StepDecorator("Job Submission")
    def submit_job(self, job_arguments):
        self.log("This is a Job Submission message")
        time.sleep(.5)
        result = ({"jobid": "02010"}, 201)
        return result

    def cancel(self):
        self.canceled = True

    def check_canceled(self):
        if self.canceled:
            raise CanceledException("Canceled")

    def log(self, message):
        self._log += "\n" + message
        self.sig_log.emit(message)

    def get_log(self):
        return self._log
    
    
    
#     def step_decorator(self, ):
#                 @functools.wraps(function)
#         def decorater_function(*args, **kwargs):
#             '''
#             The decorator function
# 
#             Tries to execute the decorated function. If an exception occurs,
#             it is caught, takes the action, and then raises the exception.
#             '''
#             assert len(args) > 0, "Must at least have self as an argument"
#             thread_instance = args[0]
# 
#             step_name = self.step_name or function.__name__
#             thread_instance.sig_step_started.emit("Running: %s" % step_name)
#             result = function(*args, **kwargs)
#             thread_instance.sig_step_finished.emit("Finished: %s" % step_name)
#             return result
# 
#         return decorater_function
    
    
    
    def step_decorator(self, function):
    
        '''
        DECORATOR
        Wraps the decorated function/method so that if the function raises an
        exception, the exception will be caught, it's message will be printed,
        and the function will return (suppressing the exception) .
        '''
        @functools.wraps(function)
        def decorater_function(*args, **kwargs):
            '''
            The decorator function

            Tries to execute the decorated function. If an exception occurs,
            it is caught, takes the action, and then raises the exception.
            '''
            assert len(args) > 0, "Must at least have self as an argument"
            thread_instance = args[0]

            step_name = self.step_name or function.__name__
            thread_instance.sig_step_started.emit("Running: %s" % step_name)
            result = function(*args, **kwargs)
            thread_instance.sig_step_finished.emit("Finished: %s" % step_name)
            return result

class JobProgressDialog(QtGui.QMessageBox):

    '''
    TBC:
        1. Want to have two different dialog boxes:
            a. progress dialog box
            b. result dialog box
        
        2. The progress dialog box will
            a.Show current step of action
            b.progress bar
            c.details button to show the "log" of the progress
            
        3. The result dialog will have
            a. The reults of the submissin : exceptions, success
            b. details of the process (take this from the log of the progress)
            
         
    '''

    link_color = "rgb(200,100,100)"
    steps = []
    is_thread_finished = False
#     minimum_width = 500

    sig_canceled = QtCore.Signal(object)

    def __init__(self, qthread, title="", text="", parent=None):
        super(JobProgressDialog, self).__init__(parent=parent)
        self.qthread = qthread






        self.setText(text)
#         self.label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.setWindowTitle(title)
        self.setStandardButtons(QtGui.QMessageBox.Cancel)
        self.progress_bar = QtGui.QProgressBar()
        self.progress_bar.setMaximum(0)
        layout = self.layout()
        layout.addWidget(self.progress_bar, 1, 1)
#         self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowCloseButtonHint)
        self.setDetailedText(" ")


        self.connect_thread()


    def connect_thread(self):


        for step in self.qthread.steps:
            self.add_step(step)

        self.qthread.sig_step_started.connect(self.step_started)
        self.qthread.sig_step_finished.connect(self.step_finished)


        # Connect the thread's finished signal to the dialog's accept slot.  This will hide the dialog once the thread has finished
        self.qthread.finished.connect(self.accept)

        # Connect the Cancel button to the cancel
        self.button(QtGui.QMessageBox.Cancel).clicked.connect(self.cancel)

        self.qthread.sig_log.connect(self.add_to_details)


    def done(self, return_code):
        '''
        This is a super hack to work around a QT bug.  When using using StandardButtons
        in a QMessageBox, when the buttons are pressed, the QMessageBox won't
        emit the expected signals (rejected(), accepted(), etc). 
        see https://forum.qt.io/topic/20663/problems-with-signal-accept-and-signal-reject-and-qmessagebox/6 
        '''
        if return_code == QtGui.QMessageBox.Cancel:
            print "done: cancelled"
            self.cancel()
            while not self.qthread.isFinished():
                QtGui.qApp.processEvents()
        super(JobProgressDialog, self).done(return_code)

    def submission_finished(self, result):
        print "submission_finished!!!!  Setting dialog to done:", result
        self.done(0)

    def add_step(self, step_description):
        self.steps.append(step_description)
        self.progress_bar.setMaximum(self.progress_bar.maximum() + 1)

    def add_to_details(self, text):
        details = "%s\n%s" % (self.detailedText(), text)
        self.setDetailedText(details)

    def next_step(self):
        next_step = self.progress_bar.value() + 1
        step_message = self.steps[next_step]
        new_value = next_step
        self.progress_bar.setValue(new_value)
        self.setText(step_message)
        if new_value >= self.progress_bar.maximum():
            self.setStandardButtons(QtGui.QMessageBox.Ok)

    def step_started(self, step_message):
        print "step started: %s" % step_message
        self.next_step()

    def step_finished(self, step_message):
        print "step finished: %s" % step_message


    def cancel(self):
        '''
        Set the dialog's test to "Cancelling <step name> ..."
        and tell the thread to cancel
        '''
        self.setText("Canceling ...")
        self.qthread.cancel()





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


        # Create widgets
        self.createUI()

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
    def runUiStandalone(cls):
        '''
        Note that this UI class is to be run directly from a python shell, e.g.
        not within another software's context (such as maya/nuke).
        '''
        global _parent_window  # This global statement is particularly important (though it may not appear so when using simple usecases that don't use complex inheritence structures).

        _parent_window = cls.getParentWindow()

        app = QtGui.QApplication.instance()
        if app is None:
            app = QtGui.QApplication(sys.argv)
        ui = cls()
        ui.show()
        app.exec_()


    @classmethod
    @pyside_utils.wait_cursor
    def runUi(cls, force_new=False):
        '''
        Launch the submitter UI.  This is intended to be run within a software 
        context such as Maya or Nuke (as opposed to a shell).  By default, 
        this will show any existing submitter UI that had been closed prior by
        the user (as opposed to creating a new instance of the UI). Use the 
        force_new flag to force a new instance of it.
        
        '''
        global _parent_window  # This global statement is particularly important (though it may not appear so when using simple usecases that don't use complex inheritence structures).
        global _ui_instance


        # Reuse the same parent window object, otherwise ownshership gets jacked, and child widgets start getting deleted. This took about 3 hours to figure out.
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




    def createUI(self):
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

        # Add the extended widget (must be implemented by the child class
        self._addExtendedWidget()


    def populateUi(self):
        '''
        Populate the UI with data.  This data should be global information that
        is not specific to the open file
        '''

        # Populate the Instance Type combobox with the available instance configs
        self.populateInstanceTypeCmbx()

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

        # Set the default instance type
        self.setInstanceType(self.default_instance_type)

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
        Return the UI's Notificaiton field
        '''
        return str(self.ui_notify_lnedt.text())

    def setNotifications(self, value):
        '''
        Set the UI's Notification field to the given value
        '''
        self.ui_notify_lnedt.setText(str(value))


    def getScoutJobCheckbox(self, off_when_disabled=True):
        '''
        Return the checkbox value for the "Scout Job" checkbox 
        '''
        if off_when_disabled and not self.ui_scout_job_chkbx.isEnabled():
            return False
        return self.ui_scout_job_chkbx.isChecked()

    def setScoutJobCheckbox(self, bool_):
        '''
        Set the checkbox value for the "Scout Job" checkbox 
        '''
        return self.ui_scout_job_chkbx.setChecked(bool_)


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

    def getJobArgs(self):
        '''
        Return a dictionary which contains the necessary conductor argument names
        and their values.  This dictionary will ultimately be passed directly 
        into a conductor Submit object when instantiating/calling it.
        
        Generally, the majority of the values that one would populate this dictionary
        with would be found by quering this UI, e.g.from the "frames" section of ui.
           
        '''
        job_args = {}

        job_args["cmd"] = self.getCommand()
        job_args["cores"] = self.getInstanceType()['cores']
        job_args["enforced_md5s"] = self.getEnforcedMd5s()
        job_args["environment"] = self.getEnvironment()
        job_args["frames"] = self.getFrameRangeString()
        job_args["chunk_size"] = self.getChunkSize()
        job_args["job_title"] = self.getJobTitle()
        job_args["local_upload"] = self.getLocalUpload()
        job_args["machine_type"] = self.getInstanceType()['flavor']
        job_args["notify"] = self.getNotifications()
        job_args["output_path"] = self.getOutputDir()
        job_args["project"] = self.getProject()
        job_args["scout_frames"] = self.getScoutFrames()
        job_args["software_package_ids"] = self.getSoftwarePackageIds()
        job_args["upload_only"] = self.getUploadOnly()
        job_args["upload_paths"] = self.getUploadPaths()

        return job_args


    def getUploadPaths(self):
        upload_paths = []
        # Get all files that we want to have integrity enforcement when uploading via the daemon
        enforced_md5s = self.getEnforcedMd5s()
        # add md5 enforced files to dependencies. In theory these should already be included in the raw_dependencies, but let's cover our bases
        upload_paths.extend(enforced_md5s.keys())
        return upload_paths


    def validateJobArgs(self, job_args):
        '''
        Validate the the given job arguments
        '''
        self.validateJobPackages()
        self.validateUploadPaths(job_args["upload_paths"])
        return job_args


    def validateUploadPaths(self, upload_paths):
        '''
        This is an added method (i.e. not a base class override), that allows
        validation to occur when a user presses the "Submit" button. If the
        validation fails, a notification dialog appears to the user, halting
        the submission process. 
        
        Validate that the data being submitted is...valid.
        
        1. Dependencies
        2. Output dir
        '''
        # Process all of the dependendencies. This will create a dictionary of dependencies, and whether they are considred Valid or not (bool)
        path_results = file_utils.validate_paths(upload_paths)

        invalid_filepaths = [path for path, is_valid in path_results.iteritems() if not is_valid]
        if invalid_filepaths:
            message = "Found invalid filepaths:\n\n%s" % "\n\n".join(invalid_filepaths)
            raise ValidationException(message)



    def getLocalUpload(self):
        '''
        Return a bool indicating whether the uploading process should occur on
        this machine or whether it should get offloaded to the uploader daemon.
        If False, uploading will occur on the daemon.
        
        Simply return the value set in the config.yml.  In the future this option
        may be exposed in the UI
        '''
        return CONFIG.get("local_upload")


    def getUploadOnly(self):
        '''
        Return whether the "Upload Only" checkbox is checked on or off.
        '''
        return self.ui_upload_only_chkbx.isChecked()

    def setUploadOnly(self, upload_only):
        '''
        Set the the "Upload Only" checkbox to the given upload_only value (bool)
        '''
        return self.ui_upload_only_chkbx.setChecked(bool(upload_only))


    def launch_result_dialog(self, response, response_code, details=""):

        # If the job submitted successfully
        if response_code in SUCCESS_CODES_SUBMIT:
            job_id = str(response.get("jobid") or 0).zfill(5)
            title = "Job Submitted"
            job_url = CONFIG['url'] + "/job/" + job_id
            message = ('<html><head/><body><p>Job submitted: '
                       '<a href="%s"><span style=" text-decoration: underline; '
                       'color:%s;">%s</span></a></p></body></html>') % (job_url, self.link_color, job_id)
            pyside_utils.launch_message_box(title, message, is_richtext=True, parent=self, details=details)
        # All other response codes indicate a submission failure.
        else:
            title = "Job Submission Failure"
            message = "Job submission failed: error %s" % response_code
            pyside_utils.launch_error_box(title, message, parent=self, details=details)


    @QtCore.Slot(bool, name="on_ui_start_end_rdbtn_toggled")
    def on_ui_start_end_rdbtn_toggled(self, on):

        self.ui_start_end_wgt.setEnabled(on)
        self.ui_custom_wgt.setDisabled(on)



    @QtCore.Slot(bool, name="on_ui_upload_only_chkbx_toggled")
    def on_ui_upload_only_chkbx_toggled(self, toggled):
        '''
        When the "Upload Only" checkbox is checked on, disable the extended
        widget (i.e. the software specific options e.g. Render layers or Write 
        nodes,etc), as well as the Scout Job checkbox.   
        When the the Upload Only checkobx is checked off, re-enable all of those
        other widgets
        '''
        if self.extended_widget:
            self.extended_widget.setDisabled(toggled)

        self.ui_scout_job_chkbx.setDisabled(toggled)


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
        
        
        The Job submission process occurs in a separate thread.  This allows
        the main thread (which runs the UI) to remain responsive.  While the 
        submission thread is running, a modal progress dialog will block the user
        until the submission thread completes. 
        
        
        
        '''
        # Creaat the submission thread
        submission_thread = SubmissionThread(self)

        # Instantiate the Submission Dialog
        job_progress_dialog = JobProgressDialog(submission_thread, title="Job Submission", text="Submitting Job", parent=self)

        # Start the submission thread.  This does NOT block the main thread from continuing
        submission_thread.start()

        # Display the modal dialog.  This DOES block the main thread from continuing.
        result = job_progress_dialog.exec_()

        # Wait for the thread to finish, otherwise the results/exception attributes may not have populated
        # This typiacally wouln't be required, but the actual termination of the
        # thread may take some time. We don't want the main thread (and UI) to be
        # free for the user to take further actions. Otherwise, this could lead to
        # the user spawning another submission process before the other one is
        # completed.  Also, losing a QThread refefence before it finishes can
        # cause a hard crash.  Once the thread finishes, the submission dialog
        # will close.
        submission_thread.wait()



        logger.debug("result: %s", result)
        logger.debug("submission_thread.result: %s", submission_thread.result)
        logger.debug("submission_thread.exception: %s", submission_thread.exception)

        thread_log = submission_thread.get_log()

        # If an excepton occured, display the exception info in a new dialog
        if submission_thread.exception:

            # Figure out what exception type occured
            e_type, e_value, e_traceback = submission_thread.exception

            # If the exception was a validation exception
            if e_type == ValidationException:
                title = "Validation Failure"
                message = e_value
                # Switch to the Software Packages tab
                self.ui_tabwgt.setCurrentIndex(self._job_software_tab_idx)
                pyside_utils.launch_error_box(title, message, self, details=thread_log)

            # If the exception was due to the user cancelling
            elif e_type == CanceledException:
                title = "Job submission Cancelled"
                message = "Job submission Cancelled"
                pyside_utils.launch_error_box(title, message, self, details=thread_log)

            # Catch all other exceptions here.  Hopefully thisw won't happen too often
            else:
                title = "Job submission failure"
                message = "".join(traceback.format_exception(*submission_thread.exception))
                pyside_utils.launch_error_box(title, message, self, details=thread_log)

        # If no excepton occured, then retrieve the response from the thread and
        # display the results in a new dialog
        else:
            response, response_code = submission_thread.result
            self.launch_result_dialog(response, response_code, details=thread_log)



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
            self.saveJobPackagesToPrefs()
            source_filepath = self.getSourceFilepath()
            self.prefs.saveSubmitterUserPrefs(source_filepath)
            self.prefs.sync()
        except:
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
        enforced_md5s = {}
        if not self.getLocalUpload():
            enforced_files = []
            enforced_files.append(self.getSourceFilepath())

            # Generate md5s to dictionary
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


    @common.ExceptionLogger("Failed to save Conductor user preferences. You may want to reset your preferences from the options menu")
    def saveScoutJobPref(self, is_checked):
        '''
        Save the "Scout Job" checkbox user preference for the open file
        '''
        filepath = self.getSourceFilepath()
        widget_name = self.sender().objectName()
        return self.prefs.setFileWidgetPref(filepath, widget_name, bool(is_checked))



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
                matched_packages.append(package_id)



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


        return matched_packages


    def saveJobPackagesToPrefs(self):
        package_ids = []
        for item in pyside_utils.get_top_level_items(self.ui_job_software_trwgt):
            package_ids.append(item.package_id)
        filepath = self.getSourceFilepath()
        self.prefs.setJobPackagesIds(filepath, package_ids)


    ###########################################################################
    ######################  AVAILABLE SOFTWARE TREEWIDGET  - self.ui_software_versions_trwgt
    ###########################################################################

    @QtCore.Slot(name="on_ui_add_to_job_pbtn_clicked")
    def on_ui_add_to_job_pbtn_clicked(self):
        self._availableAddSelectedItems()
        try:
            self.validateJobPackages()
        except ValidationException as ve:
            self.ui_tabwgt.setCurrentIndex(self._job_software_tab_idx)
            pyside_utils.launch_error_box(ve.title, ve.message, parent=self)
            raise

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
                    plugin_parent_product_item.setFlags(QtCore.Qt.ItemIsEnabled)
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
        selected_available_packages = self.getSelectedAvailablePackages()
        if not selected_available_packages:
            return pyside_utils.launch_error_box("No packages selected",
                                                 "No packages have been selected."
                                                 "Please select at least one package before adding it to the job.",
                                                 parent=self)
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
    ######################  JOB SOFTWARE TREEWIDGET  - self.ui_job_software_trwgt
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
            raise ValidationException as ve(msg, title=title)


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
            raise ValidationException as ve(msg, title=title)

        ### LOOK FOR PRESENCE OF A HOST PACKAGE ###
        for package in self.getJobPackages():
            if package["product"] == self.product:
                break
        else:
            host_info = self.getHostProductInfo()
            title = "No software package selected for %s!" % self.product
            msg = ("No %s software package have been specified for the Job!\n\n"
                   "Please go the \"Job Software\" tab and select a one (potentially %s") % (self.product, host_info["version"])
            raise ValidationException as ve(msg, title=title)



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


class ValidationException as ve(Exception):
    def __init__(message, title=None):
        self.message = message
        self.title = title
        super(ValidationException, self).__init__(message)

class CanceledException(Exception):
    pass



if __name__ == "__main__":
    app = QtGui.QApplication.instance()
    if app is None:
        app = QtGui.QApplication(sys.argv)
    ConductorSubmitter.runUi()
