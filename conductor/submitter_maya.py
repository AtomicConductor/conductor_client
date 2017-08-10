
from conductor.lib import maya_utils, pyside_utils, file_utils, api_client, common, loggeria, package_utils
from conductor import CONFIG, submitter
from conductor.lib.lsseq import seqLister
from maya import OpenMayaUI
import os
import imp
import logging
import sys
import uuid
import Qt
from Qt import QtGui, QtCore, QtWidgets

# For backwards compatibility
if Qt.__binding__ in ('PySide'):
    from shiboken import wrapInstance
else:
    from shiboken2 import wrapInstance


try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


'''
TODO:
1. When the Upload Only argument is sent to the conductor Submit object as True, does it ignore the filepath and render layer arguments?  Or should those arguments not be given to the Submit object.
3. Cull out unused maya dependencies.  Should we exclude materials that aren't assigned, etc?
5. Validate the maya file has been saved
'''

logger = logging.getLogger(__name__)


class MayaWidget(QtWidgets.QWidget):

    # The .ui designer filepath
    _ui_filepath = os.path.join(submitter.RESOURCES_DIRPATH, 'maya.ui')

    def __init__(self, parent=None):
        super(MayaWidget, self).__init__(parent=parent)
        pyside_utils.UiLoader.loadUi(self._ui_filepath, self)
        self.createUI()

    def createUI(self):
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
            tree_item = QtWidgets.QTreeWidgetItem([render_layer_info["layer_name"],
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

    product = "maya-io"

    def __init__(self, parent=None):
        super(MayaConductorSubmitter, self).__init__(parent=parent)
        self.setMayaWindow()

    @classmethod
    def getParentWindow(cls):
        '''
        Return Maya's main QT window widget. This will be the parent widget for
        the submitter UI.
        '''
        return get_maya_window()

    def setMayaWindow(self):
        '''
        Set a few QT paramaters so that the ui plays nicely with Maya's.
        '''
        # Set a unique object name string so Maya can easily look it up
        self.setObjectName('%s_%s' % (self.__class__.__name__, uuid.uuid4()))
        # Make this widget appear as a standalone window even though it is parented
        self.setWindowFlags(QtCore.Qt.Window)

    def applyDefaultSettings(self):
        super(MayaConductorSubmitter, self).applyDefaultSettings()
        start, end = maya_utils.get_frame_range()[0]
        self.setFrameRange(start, end)
        self.extended_widget.refreshUi()
        self.setOutputDir(maya_utils.get_image_dirpath())

    def getExtendedWidget(self):
        return MayaWidget()

    def generateTasksData(self):
        '''
        Return a list of tasks data.  Each item in the list represents one
        task of work that will be created.

        Each task dictionary has the following
        keys:
            command: The command for the task to execute

            frames: [optional], helps to bind/display the relationship between a
                     task and the frames that the task is operating on.  Because
                     a task can be any arbitrary command, the notion of "frames"
                     may not be relevant and can be left empty.

        Eventually we may want to populate this with *everything* a task needs
        (offloading it from the Job entity). This would allow more per-task flexiblity (such as differing environments,
        files, etc).  Just general containment in general.


        Example(two tasks):

            # Task 0
            [ {"command": "Render -s 1 -e 1 -rl renderlayer1 maya_filepath.ma"
               "frames": "1"},
            # Task 1
            {"command": "Render -s 10 -e 20 -b 2 maya_filepath.ma"
             "frames": "10-20x2"} ]
        '''

        # Create a template command that be be used for each task's command
        cmd_template = "Render -s %s -e %s -b %s %s -rd /tmp/render_output/ %s"

        # Retrieve the source maya file
        maya_filepath = self.getSourceFilepath()
        # Strip the lettered drive from the filepath (if one exists).
        # This is a hack to allow a Windows filepath to be properly used
        # as an argument in a linux shell on the backend. Not pretty.
        maya_filepath_nodrive = os.path.splitdrive(maya_filepath)[-1]

        # Get the user-selected render layers
        render_layers = self.extended_widget.getSelectedRenderLayers()
        render_layer_args = "-rl " + ",".join(render_layers)

        chunk_size = self.getChunkSize()
        frames_str = self.getFrameRangeString()
        frames = seqLister.expandSeq(frames_str.split(","), None)

        # Use the task frames generator to dispense the appropriate amount of
        # frames per task, generating a command for each task to execute
        tasks_data = []
        frames_generator = submitter.TaskFramesGenerator(frames, chunk_size=chunk_size, uniform_chunk_step=True)
        for start_frame, end_frame, step, task_frames in frames_generator:
            task_cmd = cmd_template % (start_frame,
                                       end_frame,
                                       step,
                                       render_layer_args,
                                       maya_filepath_nodrive)

            # Generate tasks data
            # convert the list of frame ints into a single string expression
            # TODO:(lws) this is silly. We should keep this as a native int list.
            task_frames_str = ", ".join(seqLister.condenseSeq(task_frames))
            tasks_data.append({"command": task_cmd,
                               "frames":  task_frames_str})
        return tasks_data

    def collectDependencies(self):
        '''
        Generate a list of filepaths that the current maya scene is dependent on.
        '''
        # Get all of the node types and attributes to query for external filepaths on
        resources = common.load_resources_file()
        dependency_attrs = resources.get("maya_dependency_attrs") or {}

        return maya_utils.collect_dependencies(dependency_attrs)

    def getEnvironment(self):
        '''
        Return a dictionary of environment variables to use for the Job's
        environment
        '''
        environment = super(MayaConductorSubmitter, self).getEnvironment()
        ocio_config = maya_utils.get_ocio_config()
        if ocio_config:
            environment.update({"OCIO": ocio_config})
        return environment

    # THIS IS COMMENTED OUT UNTIL WE DO DYNAMIC PACKAGE LOOKUP
#     def getHostProductInfo(self):
#         return maya_utils.MayaInfo.get()

    def getHostProductInfo(self):
        host_version = maya_utils.MayaInfo.get_version()
        package_id = package_utils.get_host_package(self.product, host_version, strict=False).get("package")
        host_info = {"product": self.product,
                     "version": host_version,
                     "package_id": package_id}
        return host_info


# THIS IS COMMENTED OUT UNTIL WE DO DYNAMIC PACKAGE LOOKUP
#     def getPluginsProductInfo(self):
#         return maya_utils.get_plugins_info()

    def getPluginsProductInfo(self):
        plugins_info = []
        host_version = maya_utils.MayaInfo.get_version()
        for plugin_product, plugin_version in maya_utils.get_plugin_info().iteritems():
            package_id = package_utils.get_plugin_package_id(self.product, host_version, plugin_product, plugin_version, strict=False)
            plugin_info = {"host_product": self.product,
                           "host_version": host_version,
                           "product": plugin_product,
                           "version": plugin_version,
                           "package_id": package_id}

            plugins_info.append(plugin_info)
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

        raw_dependencies = self.collectDependencies()

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

        # If the renderer is arnold and "use .tx files is enabled", then add corresponding tx files.
        # TODO:(lws) This process shouldn't happen here. We can't keep tacking on things for random
        # software-specific behavior. We're going to need start seperating behavior via classes (perhaps
        # one for each renderer type?)
        if maya_utils.is_arnold_renderer() and maya_utils.is_arnold_tx_enabled():
            tx_filepaths = file_utils.get_tx_paths(dependencies.keys(), existing_only=True)
            processed_tx_filepaths = file_utils.process_dependencies(tx_filepaths)
            dependencies.update(processed_tx_filepaths)

        raw_data = {"dependencies": dependencies}

        is_valid = self.runValidation(raw_data)
        return {"abort": not is_valid,
                "dependencies": dependencies,
                "enforced_md5s": enforced_md5s}

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
        maya_filepath = self.getSourceFilepath()
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
        conductor_args = super(MayaConductorSubmitter, self).generateConductorArgs(data)

        # check if the user has indicated that this is an upload-only job (no tasks)
        conductor_args["upload_only"] = self.extended_widget.getUploadOnlyBool()

        # Construct the maya-specific commands for each task. Only provide task data if the job is not an upload-only job
        conductor_args["tasks_data"] = self.generateTasksData() if not conductor_args["upload_only"] else None

        # Get the maya-specific environment
        conductor_args["environment"] = self.getEnvironment()

        # Grab the enforced md5s files from data (note that this comes from the presubmission phase
        conductor_args["enforced_md5s"] = data.get("enforced_md5s") or {}

        # Grab the file dependencies from data (note that this comes from the presubmission phase
        conductor_args["upload_paths"] = (data.get("dependencies") or {}).keys()
        return conductor_args

    def runConductorSubmission(self, data):

        # If an "abort" key has a True value then abort submission
        if data.get("abort"):
            logger.warning("Conductor: Submission aborted")
            return data

        return super(MayaConductorSubmitter, self).runConductorSubmission(data)

    def getSourceFilepath(self):
        '''
        Return the currently opened maya file
        '''
        return maya_utils.get_maya_scene_filepath()

    def validateJobPackages(self):
        '''
        Validate that job packages make sense
            1. ensure no duplicate packages (call the parent class method for this)
            2. ensure that no two packages of the same product exist (call the parent class method for this)
            3. Ensure that a package for the host product has been selected (call the parent class method for this)
            4. Ensure that a render package is present (unless just using maya software)
        '''
        is_valid = super(MayaConductorSubmitter, self).validateJobPackages()
        active_renderer = maya_utils.get_active_renderer()

        # If the renderer is other than mayasoftware, ensure that there is a job package for it
        if active_renderer != "mayaSoftware":
            #  get info for the active renderer
            renderer_info = maya_utils.get_renderer_info(renderer_name=active_renderer)
            PluginInfoClass = maya_utils.get_plugin_info_class(renderer_info["plugin_name"])
            plugin_product = PluginInfoClass.get_product()
            for package in self.getJobPackages():
                if package["product"] == plugin_product:
                    break
            else:
                title = "No package specified for %s!" % plugin_product
                msg = ("No %s software package has been specified for the Job!\n\n"
                       "Please go the \"Job Software\" tab and add one that is "
                       "appropriate (potentially %s") % (plugin_product, PluginInfoClass.get_version())
                pyside_utils.launch_error_box(title, msg, parent=self)
                self.ui_tabwgt.setCurrentIndex(self._job_software_tab_idx)
                return False

        return is_valid


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
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setHeaderItem(QtWidgets.QTreeWidgetItem(["Layer", "Camera"]))


def get_maya_window():
    '''
    Return the Qt instance of Maya's MainWindow
    '''
    mainWindowPtr = OpenMayaUI.MQtUtil.mainWindow()
    return wrapInstance(long(mainWindowPtr), QtWidgets.QMainWindow)
