
import os
import imp
import sys
import uuid
from PySide import QtGui, QtCore
from shiboken import wrapInstance
from maya import OpenMayaUI

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import conductor
import conductor.setup
from conductor.lib import maya_utils, pyside_utils, file_utils, api_client, common
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
        global maya_window  # This global statement is particularly important (though it may not appear so when using simple usecases that don't use complex inheritence structures).
        maya_window = get_maya_window()
        ui = cls(parent=maya_window)
        ui.show()

    def __init__(self, parent=None):
        super(MayaConductorSubmitter, self).__init__(parent=parent)
        self.setMayaWindow()
        self.refreshUi()

    def initializeUi(self):
        super(MayaConductorSubmitter, self).initializeUi()


    def setMayaWindow(self):
        '''
        Set a few QT paramaters so that the ui plays nicely with Maya's.
        '''
        # Set a unique object name string so Maya can easily look it up
        self.setObjectName('%s_%s' % (self.__class__.__name__, uuid.uuid4()))
        # Make this widget appear as a standalone window even though it is parented
        self.setWindowFlags(QtCore.Qt.Window)

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
            "-rd /tmp/render_output/ -s %f -e %f -rl render_layer1_name,render_layer2_name maya_maya_filepath.ma"
        '''
        base_cmd = "-rd /tmp/render_output/ -s %%f -e %%f %s %s"
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
        return maya_utils.collect_dependencies(maya_utils.dependency_attrs)


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


    def getDockerImage(self):
        '''
        If there is a docker image in the config.yml file, then use it (the
        parent class' method retrieves this).  Otherwise query Maya and its
        plugins for their version information, and then query  Conductor for 
        a docker image that meets those requirements. 
        '''
        docker_image = super(MayaConductorSubmitter, self).getDockerImage()
        if not docker_image:
            maya_version = maya_utils.get_maya_version()
            software_info = {"software": "maya",
                             "software_version":maya_version}
            plugin_versions = maya_utils.get_plugin_versions()
            software_info["plugins"] = plugin_versions
            docker_image = common.retry(lambda: api_client.request_docker_image(software_info))

        return docker_image


    def getJobTitle(self):
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
        maya_filepath = maya_utils.get_maya_scene_filepath()
        _, maya_filename = os.path.split(maya_filepath)

        # Cross-reference all renderable renderlayers in the maya scene with
        # the renderlayers that the user has selected in the UI.  If there is
        # a 1:1 match, then don't list any render layers in the job title (as
        # it is assumed that all will be rendered).  If there is not a 1:1
        # match, then add the render layers to the title which the user has
        # selected in the UI
        selected_render_layers = self.extended_widget.getSelectedRenderLayers()

        all_renderable_layers = []
        for render_layer_info in maya_utils.get_render_layers_info():
            if render_layer_info['renderable']:
                all_renderable_layers.append(render_layer_info['layer_name'])

        # If all render layers are being rendered, then don't specify them in the job title
        if set(all_renderable_layers) == set(selected_render_layers):
            render_layer_str = ""
        # Otherwise specify the user-selected layers in the job title
        else:
            render_layer_str = " - " + ", ".join(selected_render_layers)

        title = "MAYA - %s%s" % (maya_filename, render_layer_str)
        return title


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
        conductor_args = {}
        conductor_args["cmd"] = self.generateConductorCmd()
        conductor_args["cores"] = self.getInstanceType()['cores']
        conductor_args["job_title"] = self.getJobTitle()
        conductor_args["machine_type"] = self.getInstanceType()['flavor']
        conductor_args["force"] = self.getForceUploadBool()
        conductor_args["frames"] = self.getFrameRangeString()
        conductor_args["docker_image"] = self.getDockerImage()
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
            return data

        return super(MayaConductorSubmitter, self).runConductorSubmission(data)





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


def get_maya_window():
    '''
    Return the Qt instance of Maya's MainWindow
    '''
    mainWindowPtr = OpenMayaUI.MQtUtil.mainWindow()
    return wrapInstance(long(mainWindowPtr), QtGui.QMainWindow)


