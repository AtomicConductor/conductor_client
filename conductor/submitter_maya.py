
import os
import sys
from PySide import QtGui, QtCore

import imp

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import conductor
import conductor.setup
from conductor.lib import maya_utils, pyside_utils, file_utils
from conductor import submitter



'''
TODO: 
1. When the Upload Only argument is sent to the conductor Submit object as True, does it ignore the filepath and render layer arguments?  Or should those arguments not be given to the Submit object.
2. implement pyside inheritance to Maya's window interface
3. Cull out unused maya dependencies.  Should we exclude materials that aren't assigned, etc?
5. Validate the maya file has been saved
'''

logger = conductor.setup.logger

class MayaWidget(QtGui.QWidget):

    # The .ui designer filepath
    _ui_filepath = os.path.join(submitter.RESOURCES_DIRPATH, 'maya.ui')

    def __init__(self, parent=None):
        super(MayaWidget, self).__init__(parent=parent)
        pyside_utils.UiLoader.loadUi(self._ui_filepath, self)
        self.initializeUi()
        self.refreshUi()

    def initializeUi(self):
        self.ui_render_layers_trwgt = MayaCheckBoxTreeWidget()
        treewgt_layout = self.ui_render_layers_grpbx.layout()
        treewgt_layout.insertWidget(0, self.ui_render_layers_trwgt)


    def refreshUi(self):
        render_layers_info = maya_utils.get_render_layers_info()
        self.populateRenderLayers(render_layers_info)


    def populateRenderLayers(self, render_layers_info):
        '''
        Populate each render layer into the UI QTreeWidget.
        If the render layer has been set to renderable in maya, then check its
        qtreewidgetitem's checkbox (on) the the render layer  UI.  Only render 
        layers that are checked on will be rendered
        '''
        self.ui_render_layers_trwgt.clear()
        assert isinstance(render_layers_info, list), "render_layers argument must be a list. Got: %s" % type(render_layers_info)
        for render_layer_info in reversed(render_layers_info):
            tree_item = QtGui.QTreeWidgetItem([render_layer_info["layer_name"],
                                               render_layer_info["camera_shortname"]])

            tree_item.setFlags(tree_item.flags() | QtCore.Qt.ItemIsUserCheckable)
            tree_item._camera_transform = render_layer_info["camera_transform"]
            self.ui_render_layers_trwgt.addTopLevelItem(tree_item)

            # If the render layer is set to renderable, then check the item's checkbox on
            if render_layer_info["renderable"]:
                tree_item.setCheckState(0, QtCore.Qt.Checked)
            else:
                tree_item.setCheckState(0, QtCore.Qt.Unchecked)


        self.ui_render_layers_trwgt.resizeColumnToContents(0)

    def getSelectedRenderLayers(self):
        '''
        Return the names of the render layers that have their checkboxes checked on
        '''
        selected_layers = []
        for row_idx in range(self.ui_render_layers_trwgt.topLevelItemCount()):
            item = self.ui_render_layers_trwgt.topLevelItem(row_idx)
            if item.checkState(0) == QtCore.Qt.Checked:
                selected_layers.append(item.text(0))
        return selected_layers


    def getUploadOnlyBool(self):
        '''
        Return whether the "Upload Only" checkbox is checked on or off.
        '''
        return self.ui_upload_only.isChecked()


    @QtCore.Slot(bool, name="on_ui_upload_only_toggled")
    def on_ui_upload_only_toggled(self, toggled):
        '''
        when the "Upload Only" checkbox is checked on, disable the Render 
        Layers widget. when the "Upload Only" checkbox is checked off, enable
        the Render Layers widget.
        '''
        self.ui_render_layers_trwgt.setDisabled(toggled)


class MayaConductorSubmitter(submitter.ConductorSubmitter):
    '''
    
    This class inherits from the generic conductor submitter and adds an additional
    widget for maya-specific data.
    
    Note that the addional widget is stored (and accessible) via the 
    self.extended_widget attribute
    
    When the UI loads it will automatically populate various information:
        1. Frame range  
        2. Render layers (with their camera)
    
    '''


    _window_title = "Conductor - Maya"

    @classmethod
    def runUi(cls):
        '''
        Load the UI
        '''
        ui = cls()
        ui.show()

    def __init__(self, parent=None):
        super(MayaConductorSubmitter, self).__init__(parent=parent)
        self.refreshUi()

    def initializeUi(self):
        super(MayaConductorSubmitter, self).initializeUi()


    def refreshUi(self):
        start, end = maya_utils.get_frame_range()[0]
        self.setFrameRange(start, end)
        self.extended_widget.refreshUi()


    def getExtendedWidget(self):
        return MayaWidget()

    def generateConductorCmd(self):
        '''
        Return the command string that Conductor will execute
        
        example:
            "maya2015Render -rd /tmp/render_output/ -s %f -e %f -rl render_layer1_name,render_layer2_name maya_maya_filepath.ma"
        '''
        base_cmd = "maya2015Render -rd /tmp/render_output/ -s %%f -e %%f %s %s"

        render_layers = self.extended_widget.getSelectedRenderLayers()
        render_layer_args = "-rl " + ",".join(render_layers)
        maya_filepath = maya_utils.get_maya_scene_filepath()
        cmd = base_cmd % (render_layer_args, maya_filepath)
        return cmd


    def collectDependencies(self):
        '''
        Generate a list of filepaths that the current maya scene is dependent on.
        '''
        # A dict of maya node types and their attributes to query for dependency filepaths
        dependency_attrs = {'file':['fileTextureName'],
                         'AlembicNode':['abc_File'],
                         'VRayMesh':['fileName'],
                         'VRaySettingsNode':['ifile', 'fnm']}

        return maya_utils.collect_dependencies(dependency_attrs)


    def runPreSubmission(self):
        '''
        Override the base class (which is an empty stub method) so that a 
        validation pre-process can be run.  If validation fails, then indicate
        that the the submission process should be aborted.   
        
        We also collect dependencies (and asdasdss) at this point and pass that
        data along...
        In order to validate the submission, dependencies must be collected
        and inspected. Because we don't want to unnessarily collect dependencies
        again (after validation succeeds), we also pass the depenencies along
        in the returned dictionary (so that we don't need to collect them again).
        '''

        raw_dependencies = self.collectDependencies()
        dependencies = file_utils.process_dependencies(raw_dependencies)
        raw_data = {"dependencies":dependencies}

        is_valid = self.runValidation(raw_data)
        return {"abort":not is_valid,
                "dependencies":dependencies}


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
            skip_time_check: bool?
            upload_dependent: int? jobid?
            upload_file: str , the filepath to the dependency text file 
            upload_only: bool
            upload_paths: list of str?
            usr: str
        '''
        conductor_args = {}
        conductor_args["cmd"] = self.generateConductorCmd()
        conductor_args["cores"] = self.getInstanceType()
        conductor_args["force"] = self.getForceUploadBool()
        conductor_args["frames"] = self.getFrameRangeString()
        conductor_args["output_path"] = maya_utils.get_image_dirpath()
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
            logger.info("Conductor: Submission aborted")
            return

        super(MayaConductorSubmitter, self).runConductorSubmission(data)





class MayaCheckBoxTreeWidget(pyside_utils.CheckBoxTreeWidget):

    icon_filepath_checked = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_on_greenx_8x7.png')
    icon_filepath_unchecked = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_off_redx_8x7.png')
    icon_filepath_checked_disabled = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_on_greenx_disabled_8x7.png')
    icon_filepath_unchecked_disabled = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_off_redx_disabled_8x7.png')

    def __init__(self, parent=None):
        super(MayaCheckBoxTreeWidget, self).__init__(parent=parent)


    def initializeUi(self):
        super(MayaCheckBoxTreeWidget, self).initializeUi()
        self.setIndentation(0)
        self.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.setHeaderItem (QtGui.QTreeWidgetItem(["Layer", "Camera"]))





