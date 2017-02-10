import logging
import os
import sys
from PyQt4 import Qt, QtGui, QtCore, uic
import imp
from functools import wraps
import traceback

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conductor import CONFIG
from conductor.lib import file_utils, common, api_client, conductor_submit
from conductor import clarisse_utils, clarisse_resources

import pyqt_clarisse

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


class ClarisseConductorSubmitter(object):
    '''
    The class is PyQt front-end for submitting Clarisse renders to Conductor.
    To launch the UI, simply call self.runUI method.
    
    This class serves as an implemenation example of how one might write a front 
    end for a Conductor submitter for Clarisse.  This class is designed to be ripped
    apart of subclassed to suit the specific needs of a studio's pipeline. 
    Have fun :) 
    '''

    _window_title = "Conductor - Clarisse"
    ui = None

    def __init__(self, parent=None):
        return


    #  Actually launch and initialize the UI
    def runUi(self):
        '''
        Launch the UI
        '''
        self.app = QtGui.QApplication(["Clarisse"])
        self.ui = uic.loadUi(os.path.join(RESOURCES_DIRPATH, 'clarisse.ui'))

        self.initializeUi()

        self.ui.show()
        pyqt_clarisse.exec_(self.app)
        # self.app.exec_()


    def initializeUi(self):
#        self.ui.ui_start_frame_lnedt.setValidator(QtGui.QIntValidator())
#        self.ui.ui_end_frame_lnedt.setValidator(QtGui.QIntValidator())
        self.ui.ui_start_end_wgt.setEnabled(True)
        self.ui.ui_custom_wgt.setDisabled(True)

        #  Populate instance type combo box
        self.ui.ui_instance_type_cmbx.clear()
        for instance_info in INSTANCES:
            qv = QtCore.QVariant(instance_info)
            self.ui.ui_instance_type_cmbx.addItem(instance_info['description'], qv)

        # item_idx = self.ui.ui_instance_type_cmbx.findData({"cores": 16, "flavor": "standard", "description": "16 core, 60.0GB Mem"})
        item_idx = 6
        if item_idx == -1:
            raise Exception("Could not find combobox entry for core count: %s!"
                            "This should never happen!" % core_count)

        #  Connect the submit and refresh buttons
        self.ui.ui_submit_pbtn.clicked.connect(self.doSubmission)
        self.ui.ui_refresh_tbtn.clicked.connect(self.refreshUi)

        self.refreshUi()

        return self.ui.ui_instance_type_cmbx.setCurrentIndex(item_idx)


    def refreshUi(self):
        frame_range = clarisse_utils.get_frame_range()
        self.setFrameRange(int(frame_range[0]), int(frame_range[1]))
        self.populateImages()


    #  Populate the images box in the submitter UI
    def populateImages(self):
        self.ui.ui_render_images_trwgt.clear()

        render_images = clarisse_utils.get_clarisse_images()

        for render_image in render_images:
            tree_item = QtGui.QTreeWidgetItem([render_image.__str__()])

            tree_item.setFlags(tree_item.flags() | QtCore.Qt.ItemIsUserCheckable)
            self.ui.ui_render_images_trwgt.addTopLevelItem(tree_item)

            # If the render layer is set to renderable, then check the item's checkbox on
            tree_item.setCheckState(0, QtCore.Qt.Checked)
        self.ui.ui_render_images_trwgt.setHeaderLabel("Image Path")


    def doSubmission(self, something):
        """
        The submit button has been clicked. Do the stuff
        """
        #  Display a waiting cursor and message
        QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        # dialog = self.wait_message("Conductor", "Submitting Conductor Job...")

        #  Run pre-submission steps
        data = self.runPreSubmission()

        #  Do actual submission
        response_code, response = self.runConductorSubmission(data)

        #  Do post steps (currently none)
        self.runPostSubmission(response_code)

        #  Close waiting dialog and return cursor to normal state
        # dialog.done(0)
        QtGui.QApplication.restoreOverrideCursor()
        QtGui.QApplication.processEvents()

        #  Launch a little success window (hopefully)
        self.launch_result_dialog(response_code, response)


    def wait_message(self, title, message):
        """
        A dialog box will be displayed with the given message and title
        """
        dialog = QtGui.QDialog(parent=self.ui)
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
        return dialog


    def runPreSubmission(self):
        '''
        Override the base class (which is an empty stub method) so that a 
        validation pre-process can be run.  If validation fails, then indicate
        that the the submission process should be aborted.   
        
        We also collect dependencies (and asds) at this point and pass that
        data along...
        In order to validate the submission, dependencies must be collected
        and inspected. Because we don't want to unnessarily collect dependencies
        again (after validation succeeds), we also pass the depenencies along
        in the returned dictionary (so that we don't need to collect them again).
        '''

        scene_info = self.collectDependencies()
        dependencies = file_utils.process_dependencies(scene_info["dependencies"])
        output_path = scene_info['output_path']
        raw_data = {"dependencies":dependencies,
                    "output_path":[output_path],
                    "scene_file":scene_info["scene_file"]}

        is_valid = self.runValidation(raw_data)
        return {"abort":not is_valid,
                "dependencies":dependencies,
                "output_path":output_path,
                "scene_file":scene_info["scene_file"]}


    def collectDependencies(self):
        '''
        Return a list of filepaths from the scene
        '''
        scene_info = clarisse_utils.do_export()
        return scene_info


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
            print message
            # pyside_utils.launch_error_box("Invalid filepaths!", message, parent=self)
            return


        # ## Validate that there is a common root path across all of the Write
        # nodes' output paths
        output_path = raw_data["output_path"]
        if not output_path:
            message = "No common/shared output directory. All output files should share a common root!\n\nOutput files:\n    %s" % "\n   ".join(write_paths)
            # pyside_utils.launch_error_box("No common output directory!", message, parent=self)
            print message
            return

        return True


    def runConductorSubmission(self, data):

        # If an "abort" key has a True value then abort submission
        if data.get("abort"):
            print "Conductor: Submission aborted"
            return

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
            raise

        return response_code, response


    def generateConductorArgs(self, data):
        '''
        Override this method from the base class to provide conductor arguments that 
        are specific for Maya.  See the base class' docstring for more details.
        
            cmd: str
            force: bool
            frames: str
            output_path: str # The directory path that the render images are set to output to  
            postcmd: str?
            priority: int?
            project: str
            skip_time_check: bool?
            upload_dependent: int? jobid?
            upload_file: str , the filepath to the dependency text file 
            upload_only: bool
            upload_paths: list of str?
            usr: str
        '''
        instance_type = self.ui.ui_instance_type_cmbx.itemData(self.ui.ui_instance_type_cmbx.currentIndex()).toPyObject()
        conductor_args = {}
        conductor_args["cmd"] = self.generateConductorCmd(data)
        conductor_args["cores"] = str(instance_type['cores'])
        conductor_args["machine_type"] = str(instance_type['flavor'])
        conductor_args["force"] = False
        conductor_args["frames"] = self.getFrameRangeString()
        conductor_args["output_path"] = data["output_path"]
        conductor_args["project"] = str(self.ui.ui_project_lnedt.text())
        conductor_args["docker_image"] = "clarisse2.0"
        conductor_args["upload_only"] = self.ui.ui_upload_only.isChecked()
        conductor_args["job_title"] = "clarisse %s %s" % (data['scene_file'], self.getImages())

        # if there are any dependencies, generate a dependendency manifest and add it as an argument
        dependency_filepaths = data["dependencies"].keys()
        if dependency_filepaths:
            conductor_args["upload_paths"] = dependency_filepaths

        return conductor_args


    def generateConductorCmd(self, data):
        '''
        Return the command string that Conductor will execute
        
        example:
            "crender /Users/justin/Test/test.render -start_frame 2 -end_frame 20 -frame_step 1 -image scene/image
        '''
        start_frame = self.getStartFrame()
        end_frame = self.getEndFrame()
        frame_step = self.getStepFrame()
        image_str = self.getImages()
        base_cmd = "%s -start_frame %%f -end_frame %%f " % (data['scene_file'])
        base_cmd += "-frame_step %s -image %s" % (frame_step, image_str)
        return base_cmd


    #  Nothing to do at the moment
    def runPostSubmission(self, response):
        pass

    def getImages(self):
        image_str = ""
        num_images = self.ui.ui_render_images_trwgt.topLevelItemCount()
        for i in range(num_images):
            image = self.ui.ui_render_images_trwgt.topLevelItem(i)
            if image.checkState(0) == QtCore.Qt.Checked:
                image_str += "%s " % image.text(0)
        return image_str

    def getStartFrame(self):
        '''
        Return UI's start frame field
        '''
        return str(self.ui.ui_start_frame_lnedt.text())


    def getEndFrame(self):
        '''
        Return UI's end frame field
        '''
        return str(self.ui.ui_end_frame_lnedt.text())


    def getStepFrame(self):
        '''
        Set the UI's step frame spinbox value
        '''
        return str(self.ui.ui_step_frame_spnbx.text())


    def getFrameRangeString(self):
        if self.ui.ui_start_end_rdbtn.isChecked():
            return "%s-%sx%s" % (self.getStartFrame(), self.getEndFrame(), self.getStepFrame())
        else:
            return str(self.ui.ui_custom_lnedt.text())


    def setFrameRange(self, start, end):
        '''
        Set the UI's start/end frame fields
        '''
        self.setStartFrame(start)
        self.setEndFrame(end)


    def setStartFrame(self, start):
        self.ui.ui_start_frame_lnedt.setText(str(start))


    def setEndFrame(self, end):
        self.ui.ui_end_frame_lnedt.setText(str(end))


    def launch_result_dialog(self, response_code, response):
        link_color = "rgb(200,100,100)"
        if response_code in [201, 204]:
            job_id = str(response.get("jobid") or 0).zfill(5)
            title = "Job Submitted"
            job_url = CONFIG['url'] + "/job/" + job_id
            message = ('<html><head/><body><p>Job submitted: '
                       '<a href="%s"><span style=" text-decoration: underline; '
                       'color:%s;">%s</span></a></p></body></html>') % (job_url, link_color, job_id)
            self.launch_message_box(title, message, is_richtext=True)
        else:
            title = "Job Submission Failure"
            message = "Job submission failed: error %s" % response_code
            self.launch_error_box(title, message)


    def launch_message_box(self, title, message, is_richtext=False, parent=None):
        """
        Launches a very basic message dialog box with the given title and message. 
        
        is_richtext: bool. If True, willl set the given as RichText.  This will also
                     allow the text to support hyperlink behavior.
        """

        # create a QMessageBox
        dialog = QtGui.QMessageBox()

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


    def launch_error_box(self, title, message, parent=None):
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
