import os
import sys
from PyQt4 import Qt, QtGui, QtCore, uic
import imp, ix

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import conductor
from conductor.lib import file_utils, pyside_utils
from conductor import submitter

import pyqt_clarisse


'''
TODO:
1. implement pyside inheritance for Nuke's window interface
2. Validate that at least one write node is selected
3. Test file pathing on Windows. Especially file_utils manipulations.
'''

class ClarisseWidget(QtGui.QWidget):

    # The .ui designer filepath
    _parent_ui_path = os.path.join(submitter.RESOURCES_DIRPATH, 'submitter.ui')
    _ui_filepath = os.path.join(submitter.RESOURCES_DIRPATH, 'clarisse.ui')

    def __init__(self, parent=None):
        super(ClarisseWidget, self).__init__(parent=parent)
        uic.loadUi(self._ui_filepath, self)
        self.refreshUi()

    def refreshUi(self):
        pass

    def getUploadOnlyBool(self):
        '''
        Return whether the "Upload Only" checkbox is checked on or off.
        '''
        return self.ui_upload_only.isChecked()


class ClarisseConductorSubmitter():
    '''
    The class is PySide front-end for submitting Clarisse renders to Conductor.
    To launch the UI, simply call self.runUI method.
    
    This class serves as an implemenation example of how one might write a front 
    end for a Conductor submitter for Clarisse.  This class is designed to be ripped
    apart of subclassed to suit the specific needs of a studio's pipeline. 
    Have fun :) 
    '''

    _window_title = "Conductor - Clarisse"
    ui = None

    # @classmethod
    def runUi(self):
        '''
        Launch the UI
        '''
        # ui = cls()
        self.app = Qt.QApplication(["Clarisse"])
        # cls.ui = uic.loadUi(os.path.join(submitter.RESOURCES_DIRPATH, 'submitter.ui'))
        # uic.loadUi(os.path.join(submitter.RESOURCES_DIRPATH, 'clarisse.ui'))
        self.ui = uic.loadUi(os.path.join(submitter.RESOURCES_DIRPATH, 'submitter.ui'))
        extended_widget_layout = self.ui.ui_extended_container_wgt.layout()
        extended_widget_layout.addWidget(ClarisseWidget())

        self.initializeUi()

        self.ui.show()
        pyqt_clarisse.exec_(self.app)


    def __init__(self, parent=None):
        # super(ClarisseConductorSubmitter, self).__init__()
        return
        # self.refreshUi()

    def initializeUi(self):
        self.ui.ui_start_frame_lnedt.setValidator(QtGui.QIntValidator())
        self.ui.ui_end_frame_lnedt.setValidator(QtGui.QIntValidator())
        self.ui.ui_start_end_wgt.setEnabled(True)
        self.ui.ui_custom_wgt.setDisabled(True)
        frame_range = ix.application.get_current_frame_range()
        self.setFrameRange(int(frame_range[0]), int(frame_range[1]))

        #  Populate instance type combo box
        instance_types = submitter.get_conductor_instance_types()
        self.ui.ui_instance_type_cmbx.clear()
        for instance_info in instance_types:
            self.ui.ui_instance_type_cmbx.addItem(instance_info['description'], userData=instance_info)

        item_idx = self.ui.ui_instance_type_cmbx.findData({"cores": 16, "flavor": "standard", "description": "16 core, 60.0GB Mem"})
        if item_idx == -1:
            raise Exception("Could not find combobox entry for core count: %s!"
                            "This should never happen!" % core_count)
        return self.ui.ui_instance_type_cmbx.setCurrentIndex(item_idx)

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

    def refreshUi(self):
        pass

    def getExtendedWidget(self):
        return ClarisseWidget()


    def generateConductorCmd(self):
        '''
        Return the command string that Conductor will execute
        
        example:
            "nuke-render -X AFWrite.write_exr -F %f /Volumes/af/show/walk/shots/114/114_100/sandbox/mjtang/tractor/nuke_render_job_122/walk_114_100_main_comp_v136.nk"

        '''
        base_cmd = "nuke-render -F %%f %s %s"
        return base_cmd


    def collectDependencies(self):
        '''
        Return a list of filepaths that the currently selected Write nodes
        have a dependency on.
        '''

        # A dict of nuke node types, and their knob names to query for dependency filepaths
        dependency_knobs = {'Read':['file'],
                            'DeepRead':['file'],
                            'ReadGeo2':['file'],
                            'Vectorfield':['vfield_file'],
                            'ScannedGrain':['fullGrain'],
                            'Group':['vfield_file', 'cdl_path'],
                            'Precomp':['file'],
                            'AudioRead':['file'],
                            'Camera':['file'],
                            'Camera2':['file']}

        return []


    def getOutputPath(self):
        '''
        From the selected Write nodes (in the UI), query their output paths
        and derive common directory which they all share (somewhere in their
        directory tree).  Return a two-item tuple, containing the output path, and
        a list of the write node's output paths 
        '''
        return "", []

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

        raw_dependencies = self.collectDependencies()
        dependencies = file_utils.process_dependencies(raw_dependencies)
        output_path, write_paths = self.getOutputPath()
        raw_data = {"dependencies":dependencies,
                    "output_path":[output_path, write_paths]}

        is_valid = self.runValidation(raw_data)
        return {"abort":not is_valid,
                "dependencies":dependencies,
                "output_path":output_path}



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
            pyside_utils.launch_error_box("Invalid filepaths!", message, parent=self)
            return


        # ## Validate that there is a common root path across all of the Write
        # nodes' output paths
        output_path, write_paths = raw_data["output_path"]
        if not output_path:
            message = "No common/shared output directory. All output files should share a common root!\n\nOutput files:\n    %s" % "\n   ".join(write_paths)
            pyside_utils.launch_error_box("No common output directory!", message, parent=self)
            return

        return True



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
            resource: int, core count
            skip_time_check: bool?
            upload_dependent: int? jobid?
            upload_file: str , the filepath to the dependency text file 
            upload_only: bool
            upload_paths: list of str?
            usr: str
        '''
        conductor_args = {}
        conductor_args["cmd"] = self.generateConductorCmd()
        conductor_args["cores"] = self.getInstanceType()['cores']
        conductor_args["machine_type"] = self.getInstanceType()['flavor']
        conductor_args["force"] = self.getForceUploadBool()
        conductor_args["frames"] = self.getFrameRangeString()
        conductor_args["output_path"] = data["output_path"]
        conductor_args["resource"] = self.getResource()
        conductor_args["upload_only"] = self.extended_widget.getUploadOnlyBool()

        # if there are any dependencies, generate a dependendency manifest and add it as an argument
        dependency_filepaths = data["dependencies"].keys()
        if dependency_filepaths:
            conductor_args["upload_paths"] = dependency_filepaths

        return conductor_args


    def runConductorSubmission(self, data):

        # If an "abort" key has a True value then abort submission
        if data.get("abort"):
            print "Conductor: Submission aborted"
            return

        super(ClarisseConductorSubmitter, self).runConductorSubmission(data)

