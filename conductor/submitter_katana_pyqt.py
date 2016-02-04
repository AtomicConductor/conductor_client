import inspect
import logging
import os
import re
import sys
import traceback
import imp
from functools import wraps

from PyQt4 import Qt, QtGui, QtCore, uic


try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conductor import CONFIG, submitter_resources
from conductor.lib import file_utils, common, api_client, conductor_submit
from conductor.lib import katana_utils, file_utils, api_client, common, loggeria

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)
PACKAGE_DIRPATH = os.path.dirname(__file__)
RESOURCES_DIRPATH = os.path.join(PACKAGE_DIRPATH, "resources")
INSTANCES = [{"cores": 4, "flavor": "standard", "description": " 4 core, 15.0GB Mem"},
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


def wait_cursor(func):
    """
    Wraps the decorated function so that while it is running, the mouse
    cursor changes to waiting icon.
    """
    @wraps(func)
    def wrapper(*args, **kwds):
        try:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            return func(*args, **kwds)
        finally:
            QtGui.QApplication.restoreOverrideCursor()
            # Not sure if this is needed
            QtGui.QApplication.processEvents()

    return wrapper

def wait_message(title, message):
    """
    Wraps the decorated method so that while it runs, a dialog box will
    be displayed with the given message and title
    """

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwds):
            parent = args[0]  # The first argument will be the wrapped method's class instance (i.e. self), which will be used as the parent
            dialog = QtGui.QDialog(parent=parent)
            layout = QtGui.QHBoxLayout()
            dialog.label = QtGui.QLabel()
            dialog.label.setText(message)
            dialog.label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            layout.addWidget(dialog.label)
            dialog.setLayout(layout)
            dialog.setWindowTitle(title)
            dialog.show()
            # TODO: This stupid for-loop with a print statement is hack to force a redraw/update to the dialog. Otherwise it's blank. Tried a million things.  This is the only one that works..most of the time.
            for i in range(5):
                print "",
                QtGui.qApp.processEvents()
            try:
                return func(*args, **kwds)
            finally:
                dialog.done(0)
        return wrapper
    return decorator


class KatanaConductorSubmitter(QtGui.QMainWindow):
    '''
    The class is PyQt front-end for submitting Clarisse renders to Conductor.
    To launch the UI, simply call self.runUI method.
    
    This class serves as an implemenation example of how one might write a front 
    end for a Conductor submitter for Clarisse.  This class is designed to be ripped
    apart of subclassed to suit the specific needs of a studio's pipeline. 
    Have fun :) 
    '''

    _window_title = "Conductor - Katana"

    _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'submitter.ui')

    default_instance_type = 16

    link_color = "rgb(200,100,100)"



    @classmethod
    def runUi(cls):
        global ui
        ui = cls()
        ui.show()


    def __init__(self, parent=None):
        super(KatanaConductorSubmitter, self).__init__(parent=parent)
        uic.loadUi(self._ui_filepath, self)
        self.initializeUi()
        self.refreshUi()

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
        self.start_end_rdbtn_toggled(True)

        # Populate the Instance Type combobox with the available instance configs
        self.populateInstanceTypeCmbx()

        # Set the default instance type
        self.setInstanceType(self.default_instance_type)

        # Hide the widget that holds advanced settings. TODO: need to come back to this.
        self.ui_advanced_wgt.hide()

        # Hide output path.  Don't let the user dictate this. This will make the collection of the render fail on render node.
        self.ui_output_directory_lnedt.hide()

        # shrink UI to be as small as can be
        self.adjustSize()

        # Set the keyboard focus on the frame range radio button
        self.ui_start_end_rdbtn.setFocus()

        self.ui_choose_output_path_pbtn.clicked.connect(self.browseOutput)
        self.ui_submit_pbtn.clicked.connect(self.submit_pbtn_clicked)
        self.ui_refresh_tbtn.clicked.connect(self.refreshUi)
        self.ui_start_end_rdbtn.toggled.connect(self.start_end_rdbtn_toggled)
        self.ui_refresh_tbtn.clicked.connect(self.refresh_tbtn_clicked)



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

    def refreshUi(self):
        render_node = self.getRenderNode()
        self.setOutputDir(katana_utils.get_output_dirpath(render_node))
        start, end = katana_utils.get_frame_range()
        self.setFrameRange(start, end)


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
        return self.ui_instance_type_cmbx.itemData(self.ui_instance_type_cmbx.currentIndex()).toPyObject()

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

    def browseOutput(self):
        directory = str(QtGui.QFileDialog.getExistingDirectory(self, "Select Directory"))
        if not directory:
            return
        directory = re.sub("\\\\", "/", directory)
        self.setOutputDir(directory)

    def getDockerImage(self):
        return ""


    def getForceUploadBool(self):
        '''
        Return whether the "Force Upload" checkbox is checked on or off.
        '''
        return self.ui_force_upload_chkbx.isChecked()

    def getRenderNodes(self):
        katana_utils.get_render_nodes()


    def getRenderNode(self):
        '''
        demohack to return only the deadpool node
        '''
        for render_node in katana_utils.get_render_nodes():
            if render_node.getName() == "deadpool":
                return render_node

        raise Exception("No valid render_node found")


    def getJobTitle(self, katana_filepath, render_node):
        '''
        Generate and return the title to be given to the job.  This is the title
        that will be displayed in the webUI.
                
        Construct the job title by using the software name (MAYA), followed by
        the filename of maya file (excluding directory path), followed by the
        renderlayers being rendered.  If all of the renderlayers in the maya 
        scene are being rendered then don't list any of them. 
        
        MAYA - <maya filename> - <renderlayers> 
        
        example: "MAYA - my_maya_scene.ma - beauty, shadow, spec"
        '''
        _, katana_filename = os.path.split(katana_filepath)
        title = "KATANA - %s - %s" % (katana_filename, render_node.getName())
        return title


    def getLocalUpload(self):
        '''
        Return a bool indicating whether the uploading process should occur on
        this machine or whether it should get offloaded to the uploader daemon.
        If False, uploading will occur on the daemon.
        
        Simply return the value set in the config.yml.  In the future this option
        may be exposed in the UI
        '''
        return CONFIG.get("local_upload")

    def getSourceFilepath(self):
        '''
        Get the katana filepath that Conductor should upload/render.  
        '''
        return katana_utils.get_katana_filepath()


    def getEnvironment(self):
        '''
        Generate a dictionary of environment variables that will be set for the
        Conductor job. 
        
        Note that the dictionary values can refer to existing environment variables
        that are found in Conductor's environment
        
        example:
            {"PYTHONPATH":"/tmp/python:$PYTHONPATH"}
        '''
        return katana_utils.generate_env()




    def launch_result_dialog(self, response_code, response):

        # If the job submitted successfully
        if response_code in [201, 204]:
            job_id = str(response.get("jobid") or 0).zfill(5)
            title = "Job Submitted"
            job_url = CONFIG['url'] + "/job/" + job_id
            message = ('<html><head/><body><p>Job submitted: '
                       '<a href="%s"><span style=" text-decoration: underline; '
                       'color:%s;">%s</span></a></p></body></html>') % (job_url, self.link_color, job_id)
            launch_message_box(title, message, is_richtext=True, parent=self)
        # All other response codes indicate a submission failure.
        else:
            title = "Job Submission Failure"
            message = "Job submission failed: error %s" % response_code
            launch_error_box(title, message, parent=self)



    def start_end_rdbtn_toggled(self, on):

        self.ui_start_end_wgt.setEnabled(on)
        self.ui_custom_wgt.setDisabled(on)


    def submit_pbtn_clicked(self):
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

        self.launch_result_dialog(response_code, response)


    def refresh_tbtn_clicked(self):
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





    @wait_cursor
    @wait_message("Conductor", "Submitting Conductor Job...")
    def runConductorSubmission(self, data):
        '''
        Instantiate a Conductor Submit object with the given conductor_args 
        (dict), and execute it. 
        '''

        # If an "abort" key has a True value then abort submission
        if data.get("abort"):
            logger.warning("Conductor: Submission aborted")
            return data



        # Generate a dictionary of arguments to feed conductor
        conductor_args = self.generateConductorArgs(data)
#         print "conductor_args", conductor_args
#         logger.info("conductor_args %s:", conductor_args)

        # Print out the values for each argument
        logger.info("runConductorSubmission ARGS:")
        for arg_name, arg_value in conductor_args.iteritems():
            logger.info("%s: %s", arg_name, arg_value)

        # Instantiate a conductor Submit object and run the submission!
        try:
            submission = conductor_submit.Submit(conductor_args)
            response, response_code = submission.main()

        except:
            title = "Job submission failure"
            message = "".join(traceback.format_exception(*sys.exc_info()))
            launch_error_box(title, message, self)
            raise

        return response_code, response

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

    def runPreSubmission(self):
        '''
        Override the base class (which is an empty stub method) so that a 
        validation pre-process can be run.  If validation fails, then indicate
        that the the submission process should be aborted.   
        
        We also collect dependencies  at this point and pass that
        data along...
        In order to validate the submission, dependencies must be collected
        and inspected. Because we don't want to unnessarily collect dependencies
        again (after validation succeeds), we also pass the depenencies along
        in the returned dictionary (so that we don't need to collect them again).
        '''
        katana_filepath = self.getSourceFilepath()
        render_node = self.getRenderNode()

        raw_dependencies = self.collectDependencies(katana_filepath, render_node)


        # If uploading locally (i.e. not using  uploader daemon
        if self.getLocalUpload():
            # Don't need to enforce md5s for the daemon (don't want to do unnessary md5 hashing here)
            enforced_md5s = {}
        else:
            # Get all files that we want to have integrity enforcement when uploading via the daemon
            enforced_md5s = self.getEnforcedMd5s()

        # add md5 enforced files to dependencies. In theory these should already be included in the raw_dependencies, but let's cover our bases
        raw_dependencies.extend(enforced_md5s.keys())

        # Process all of the dependendencies. This will create a dictionary of dependencies, and whether they are considred Valid or not (bool)
        dependencies = file_utils.process_dependencies(raw_dependencies)


        raw_data = {"dependencies":dependencies}

        is_valid = self.runValidation(raw_data)
        return {"abort":not is_valid,
                "dependencies":dependencies,
                "enforced_md5s":enforced_md5s}



    def runValidation(self, raw_data):
        '''
        This is an added method (i.e. not a base class override), that allows
        validation to occur when a user presses the "Submit" button. If the
        validation fails, a notification dialog appears to the user, halting
        the submission process. 
        
        Validate that the data being submitted is...valid.
        
        1. Dependencies
        2. Output dir
        '''

        # ## Validate that all filepaths exist on disk
        dependencies = raw_data["dependencies"]
        invalid_filepaths = [path for path, is_valid in dependencies.iteritems() if not is_valid]
        if invalid_filepaths:
            message = "Found invalid filepaths:\n\n%s" % "\n\n".join(invalid_filepaths)
            launch_error_box("Invalid filepaths!", message, parent=self)
            raise Exception(message)

        return True



    def generateConductorArgs(self, data):
        '''
        Override this method from the base class to provide conductor arguments that 
        are specific for Maya.  See the base class' docstring for more details.

            cmd: str
            force: bool
            frames: str
            output_path: str # A directory path which shares a common root with all output files.  
            postcmd: str?
            priority: int?
            resource: int, core count
            upload_file: str , the filepath to the dependency text file 
            upload_only: bool
            upload_paths: list of str?
            usr: str
        '''
        render_node = self.getRenderNode()
        katana_filepath = self.getSourceFilepath()

        conductor_args = {}
        conductor_args["cmd"] = self.generateConductorCmd(katana_filepath, render_node)
        conductor_args["cores"] = str(self.getInstanceType()[QtCore.QString('cores')])
        conductor_args["job_title"] = self.getJobTitle(katana_filepath, render_node)
        conductor_args["machine_type"] = str(self.getInstanceType()[QtCore.QString('flavor')])

        # Grab the enforced md5s files from data (note that this comes from the presubmission phase
        conductor_args["enforced_md5s"] = data.get("enforced_md5s") or {}
        conductor_args["force"] = self.getForceUploadBool()
        conductor_args["frames"] = self.getFrameRangeString()
        conductor_args["docker_image"] = self.getDockerImage()
        conductor_args["local_upload"] = self.getLocalUpload()
        conductor_args["notify"] = self.getNotifications()
        conductor_args["output_path"] = katana_utils.get_output_dirpath(render_node)  # Don't use the UI's output path. Dangerous. Won't collect renders properly after render on render node
        conductor_args["resource"] = self.getResource()
        conductor_args["env"] = self.getEnvironment()
        # Grab the file dependencies from data (note that this comes from the presubmission phase
        conductor_args["upload_paths"] = (data.get("dependencies") or {}).keys()

        return conductor_args





    def generateConductorCmd(self, source_filepath, render_node, render_internal_dependences=True):
        base_cmd = "katana --batch  -t %%f-%%f %s %s %s"

        arg_render_internal_dependences = "--render-internal-dependencies" if render_internal_dependences else ""
        arg_render_node = "--render-node=%s" % render_node.getName()
        arg_katana_file = "--katana-file=%s" % source_filepath

        cmd = base_cmd % (arg_render_internal_dependences, arg_render_node, arg_katana_file)

        return cmd

    def collectDependencies(self, katana_filepath, render_node):
        final_paths = set()

        dep_paths = katana_utils.collect_dependencies(katana_filepath, render_node)
        for path in file_utils.process_upload_filepaths(dep_paths, strict=False):


            if not os.path.exists(path):
                logger.warning("1Path does not exist: %s", path)
                continue
            final_paths.add(path)

        return sorted(final_paths)


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

def launch_message_box(title, message, is_richtext=False, parent=None):
    """
    Launches a very basic message dialog box with the given title and message. 
    
    is_richtext: bool. If True, willl set the given as RichText.  This will also
                 allow the text to support hyperlink behavior.
    """

    # create a QMessageBox
    dialog = QtGui.QMessageBox(parent=parent)

    # Set the window title to the given title string
    dialog.setWindowTitle(str(title))

    # Set the message text to the given message string
    dialog.setText(str(message))

    # Set the text to be selectable by a mouse
    text_label = dialog.findChild(QtGui.QLabel, "qt_msgbox_label")
    text_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    if is_richtext:
        text_label.setTextInteractionFlags(text_label.textInteractionFlags() | QtCore.Qt.TextBrowserInteraction)
        text_label.setTextFormat(QtCore.Qt.RichText)
        text_label.setOpenExternalLinks(True);

    return dialog.exec_()


def launch_error_box(title, message, parent=None):
    """
    Launches a QErrorMessage dialog box with the given title and message. 
    """

    # create a QErrorMessage
    dialog = QtGui.QErrorMessage(parent=parent)

    # Set the window title to the given title string
    dialog.setWindowTitle(str(title))

    # Set the message text to the given message string
    text_document = dialog.findChild(QtGui.QTextDocument)
    text_document.setPlainText(str(message))

    # find the icon (label) and hide it (it takes up too much space)
    label = dialog.findChild(QtGui.QLabel)
    label.hide()

    # find the checkbox and hide it (it serves no purpose for us)
    checkbox = dialog.findChild(QtGui.QCheckBox)
    checkbox.hide()
    return dialog.exec_()





def get_conductor_instance_types():
    '''
    Return a dictionary which represents the different Conductor instance
    types available.  They key is the "core count" (which gets fed into
    Conductor's Submit object as an argument), and the value is the string that
    will appear in the ui to describe the instance type.
    
    TODO: This information should probably be put into and read from an external
          file (yaml, json, etc) 
    '''
    instances = [{"cores": 4, "flavor": "standard", "description": " 4 core, 15.0GB Mem"},
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
