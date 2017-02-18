
import os
import imp
import logging
import sys
from PySide import QtGui, QtCore

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conductor import submitter
from conductor.lib import clarisse_utils, pyside_utils, file_utils, package_utils

'''
TODO:
1. When the Upload Only argument is sent to the conductor Submit object as True, does it ignore the filepath and render layer arguments?  Or should those arguments not be given to the Submit object.
3. Cull out unused maya dependencies.  Should we exclude materials that aren't assigned, etc?
5. Validate the maya file has been saved
'''

logger = logging.getLogger(__name__)


class ClarisseWidget(QtGui.QWidget):

    # The .ui designer filepath
    _ui_filepath = os.path.join(submitter.RESOURCES_DIRPATH, 'clarisse.ui')

    def __init__(self, parent=None):
        super(ClarisseWidget, self).__init__(parent=parent)
        pyside_utils.UiLoader.loadUi(self._ui_filepath, self)
        self.initializeUi()
        self.refreshUi()

    def initializeUi(self):
        self.refreshUi()

    def refreshUi(self):
        self.populateImages()

    def getLayers(self):
        layers = []
        num_layers = self.ui_render_images_trwgt.topLevelItemCount()
        for i in range(num_layers):
            layer = self.ui_render_images_trwgt.topLevelItem(i)
            if layer.checkState(0) == QtCore.Qt.Checked:
                layers.append(layer.text(0))
        return layers

    #  Populate the images box in the submitter UI
    def populateImages(self):
        self.ui_render_images_trwgt.clear()

        render_images = clarisse_utils.get_clarisse_layers()
        print render_images

        for render_image in render_images:
            tree_item = QtGui.QTreeWidgetItem([render_image.__str__()])

            tree_item.setFlags(tree_item.flags() | QtCore.Qt.ItemIsUserCheckable)
            self.ui_render_images_trwgt.addTopLevelItem(tree_item)

            # If the render layer is set to renderable, then check the item's checkbox on
            tree_item.setCheckState(0, QtCore.Qt.Unchecked)
        self.ui_render_images_trwgt.setHeaderLabel("Layer Path")

    def getUploadOnlyBool(self):
        return self.ui_upload_only.isChecked()

    @QtCore.Slot(bool, name="on_ui_upload_only_toggled")
    def on_ui_upload_only_toggled(self, toggled):
        '''
        when the "Upload Only" checkbox is checked on, disable the Render
        Layers widget. when the "Upload Only" checkbox is checked off, enable
        the Render Layers widget.
        '''
        self.ui_render_images_trwgt.setDisabled(toggled)


class ClarisseConductorSubmitter(submitter.ConductorSubmitter):
    '''

    This class inherits from the generic conductor submitter and adds an additional
    widget for maya-specific data.

    Note that the addional widget is stored (and accessible) via the
    self.extended_widget attribute

    When the UI loads it will automatically populate various information:
        1. Frame range
        2. Render layers (with their camera)

    '''

    _window_title = "Conductor - Clarisse"
    product = "clarisse"
    scene_file = ""

    def __init__(self, parent=None):
        super(ClarisseConductorSubmitter, self).__init__(parent=parent)

    def applyDefaultSettings(self):
        # super(ClarisseConductorSubmitter, self).applyDefaultSettings()
        frame_range = clarisse_utils.get_frame_range()
        self.setFrameRange(int(frame_range[0]), int(frame_range[1]))
        self.extended_widget.refreshUi()
        output_path = clarisse_utils.get_clarisse_output_path()
        print("OUTPUT PATH = %s" % output_path)
        self.setOutputDir(output_path)

    def getExtendedWidget(self):
        return ClarisseWidget()

    def generateConductorCmd(self):
        '''
        Return the command string that Conductor will execute.


        example:
            "Render -rd /tmp/render_output/ <frame_args> -rl render_layer1_name,render_layer2_name maya_maya_filepath.ma"

        The <frame_args> portion of the command will have values substitited into
        into it by conductor (when the job is submitted).  These values will be
        dictated by the "frames" argument.
        '''

        layers = self.extended_widget.getLayers()
        layer_str = ""
        output_str = ""
        # image_frames_str = ""
        for layer in layers:
            print layer
            if not layer:
                continue
            output_path = clarisse_utils.get_clarisse_layer_output_path(str(layer))
            layer_str += "%s " % layer
            output_str += "%s " % output_path
            # image_frames_str += "<frame_args> "
        base_cmd = "crender %s -image %s -frames_list <frame_args> -output %s " % (self.scene_file, layer_str,
                                                                                   output_str)
        return base_cmd

    def collectDependencies(self):
        '''
        Generate a list of filepaths that the current maya scene is dependent on.
        '''
        # Get all of the node types and attributes to query for external filepaths on
        scene_info = clarisse_utils.do_export()
        self.scene_file = scene_info["scene_file"]
        return scene_info

    def getEnvironment(self):
        '''
        Return a dictionary of environment variables to use for the Job's
        environment
        '''
        environment = super(ClarisseConductorSubmitter, self).getEnvironment()
        return environment

    def getHostProductInfo(self):
        package_id = package_utils.get_host_package(self.product, clarisse_utils.get_clarisse_version(),
                                                    strict=False).get("package")
        host_info = {"product": "clarisse",
                     "version": clarisse_utils.get_clarisse_version(),
                     "package_id": package_id}
        return host_info


# THIS IS COMMENTED OUT UNTIL WE DO DYNAMIC PACKAGE LOOKUP
#     def getPluginsProductInfo(self):
#         return maya_utils.get_plugins_info()

    def getPluginsProductInfo(self):
        plugins_info = []
        # host_version = maya_utils.MayaInfo.get_version()
        # for plugin_product, plugin_version in maya_utils.get_plugin_info().iteritems():
        #     package_id = package_utils.get_plugin_package_id(self.product, host_version, plugin_product, plugin_version, strict=False)
        #     plugin_info = {"host_product": self.product,
        #                    "host_version": host_version,
        #                    "product":plugin_product,
        #                    "version":plugin_version,
        #                    "package_id": package_id}
        #
        #     plugins_info.append(plugin_info)
        return plugins_info

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

        scene_info = self.collectDependencies()
        dependencies = file_utils.process_dependencies(scene_info["dependencies"])
        output_path = scene_info['output_path']
        print output_path
        raw_data = {"dependencies": dependencies,
                    "output_path": [output_path],
                    "scene_file": self.scene_file}

        is_valid = self.runValidation(raw_data)
        return {"abort": not is_valid,
                "dependencies": dependencies,
                "output_path": output_path,
                "scene_file": self.scene_file}

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

        title = "CLARISSE %s" % self.scene_file
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

        # IF there are any error messages (stored in the dict values)
        if any(dependencies.values()):
            message = ""
            for _, error_message in dependencies.iteritems():
                if error_message:
                    message += "\n%s" % error_message

            pyside_utils.launch_error_box("Invalid file paths!", message, parent=self)
            raise Exception(message)

        return True

    def generateConductorArgs(self, data):
        '''
        Override this method from the base class to provide conductor arguments that
        are specific for Maya.  See the base class' docstring for more details.

        '''
        # Get the core arguments from the UI via the parent's  method
        conductor_args = super(ClarisseConductorSubmitter, self).generateConductorArgs(data)

        # Construct the maya-specific command
        conductor_args["cmd"] = self.generateConductorCmd()

        # Get the maya-specific environment
        conductor_args["environment"] = self.getEnvironment()

        # Grab the enforced md5s files from data (note that this comes from the presubmission phase
        conductor_args["enforced_md5s"] = data.get("enforced_md5s") or {}

        conductor_args["upload_only"] = self.extended_widget.getUploadOnlyBool()
        # Grab the file dependencies from data (note that this comes from the presubmission phase
        conductor_args["upload_paths"] = (data.get("dependencies") or {}).keys()
        return conductor_args

    def runConductorSubmission(self, data):

        # If an "abort" key has a True value then abort submission
        if data.get("abort"):
            logger.warning("Conductor: Submission aborted")
            return data

        return super(ClarisseConductorSubmitter, self).runConductorSubmission(data)

    def getSourceFilepath(self):
        '''
        Return the currently opened maya file
        '''
        return self.scene_file


    def validateJobPackages(self):
        '''
        Validate that job packages make sense
            1. ensure no duplicate packages (call the parent class method for this)
            2. ensure that no two packages of the same product exist (call the parent class method for this)
            3. Ensure that a package for the host product has been selected (call the parent class method for this)
            4. Ensure that a render package is present (unless just using maya software)
        '''
        is_valid = super(ClarisseConductorSubmitter, self).validateJobPackages()

        # If the renderer is other than mayasoftware, ensure that there is a job package for it
        # if active_renderer != "mayaSoftware":
        #     #  get info for the active renderer
        #     renderer_info = maya_utils.get_renderer_info(renderer_name=active_renderer)
        #     PluginInfoClass = maya_utils.get_plugin_info_class(renderer_info["plugin_name"])
        #     plugin_product = PluginInfoClass.get_product()
        #     for package in self.getJobPackages():
        #         if package["product"] == plugin_product:
        #             break
        #     else:
        #         title = "No package specified for %s!" % plugin_product
        #         msg = ("No %s software package has been specified for the Job!\n\n"
        #                "Please go the \"Job Software\" tab and add one that is "
        #                "appropriate (potentially %s") % (plugin_product, PluginInfoClass.get_version())
        #         pyside_utils.launch_error_box(title, msg, parent=self)
        #         self.ui_tabwgt.setCurrentIndex(self._job_software_tab_idx)
        #         return False

        return is_valid


