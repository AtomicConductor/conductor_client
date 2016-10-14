import imp
import logging
import os
import sys
import uuid
import Qt
from Qt import QtGui, QtCore, QtWidgets

# For backwards compatibility
if Qt.__binding__ in ('PySide'):
    from shiboken import wrapInstance
else:
    from shiboken2 import wrapInstance

from maya import OpenMayaUI

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conductor import CONFIG, submitter
from conductor.lib import maya_utils, pyside_utils, file_utils, common, package_utils
from conductor.lib.lsseq import seqLister


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
        self.initializeUi()
        self.refreshUi()

    def initializeUi(self):
        mainwindow = self.window()
        # Create Render Layers  TreeWidget
        self.ui_render_layers_trwgt = MayaRenderLayerTreeWidget(mainwindow._instance_types)
        treewgt_layout = self.ui_render_layers_grpbx.layout()
        treewgt_layout.insertWidget(0, self.ui_render_layers_trwgt)
        treewgt_layout.setContentsMargins(9, 9, 9, 9)

    def refreshUi(self):
        render_layers_info = maya_utils.get_render_layers_info()
        self.populateRenderLayers(render_layers_info)
        self.ui_render_layers_trwgt.resizeColumnToContents(0)
        self.ui_render_layers_trwgt.resizeColumnToContents(1)
        self.ui_render_layers_trwgt.resizeColumnToContents(2)
        self.ui_render_layers_trwgt.resizeColumnToContents(3)
        self._header_state = self.ui_render_layers_trwgt.header().saveState()
        print "resizeMode", self.ui_render_layers_trwgt.header().resizeMode(0)
        print "resizeMode", self.ui_render_layers_trwgt.header().resizeMode(1)
        print "resizeMode", self.ui_render_layers_trwgt.header().resizeMode(2)
        print "resizeMode", self.ui_render_layers_trwgt.header().resizeMode(3)

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

            tree_item._camera_transform = render_layer_info["camera_transform"]

            # If the render layer is set to renderable, then check the item's checkbox on
            self.ui_render_layers_trwgt.addTopLevelCheckboxInstanceItem(tree_item, is_checked=render_layer_info["renderable"])

        self.ui_render_layers_trwgt.resizeColumnToContents(0)

    def getLayerRows(self, checked=None, highlighted=None, names_only=False):
        '''
        Return a list of dicts where each dict describes the data in a row
        from the render layers treewidget

            [
                {"layer_name": "shadows",
                 "instance_type": n1-standard-16
                 "preemptible": False},

                {"layer_name": "specular",
                 "instance_type": n1-standard-8
                 "preemptible": False},

                {"layer_name": "reflections",
                 "instance_type": n1-standard-32
                 "preemptible": True},       
            ]
        '''
        rows = []
        for item in self.ui_render_layers_trwgt.getRowItems(checked=checked, highlighted=highlighted):
            if names_only:
                row = item.text(0)
            else:
                row = {"layer_name": item.text(0),
                       "instance_type": self.ui_render_layers_trwgt.getItemInstanceType(item),
                       "preemptible": self.ui_render_layers_trwgt.getItemPreemptible(item),
                       }
            rows.append(row)
        return rows


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

    def createUI(self):
        super(MayaConductorSubmitter, self).createUI()

        # connect signals from extended widget
        self.extended_widget.ui_layer_jobs_chkbx.toggled.connect(self.on_ui_layer_jobs_chkbx_toggled)

        # Hide the global instance type widget (instance type is implemented per render layer)
        # Hide the global preemptible checkbox (preemptible is implemented per render layer)
        self.ui_instance_wgt.setVisible(False)

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
        return MayaWidget(parent=self)

    def getJobsArgs(self):
        '''
        Return a list of two-item tuples, where the first item is dictionary
        of arguments for posting a Job resource, and the second item is a list
        of dictionaries, where each dictionary are the arguments for posting
        a Task of that Job.

            [
                # Job #1 and it's corresponding tasks
                (<job_args>, [<task_args>, 
                             <task_args>, 
                             <task_args>...] ), 

                # Job #2 and it's corresponding tasks
                (<job_args>, [<task_args>, 
                             <task_args>, 
                             <task_args>...] ) 
            ]

        Note that the resource ID's for Metadata, Upload, and Job will be handled
        by the parent class, which will inject them as/if necessary/appropriate.
        '''
        jobs_args = []

        # Get all the layers that have been checkboxed ON by the user
        layer_names = self.extended_widget.getLayerRows(checked=True, names_only=True)

        # UPLOAD-ONLY JOB
        # If an upload_only job, the
        if self.isUploadOnly():
            job_args = self.getJobArgs(layer_names)
            jobs_args.append((job_args, []))

        # MULTIPLE RENDER JOBS
        elif self.isMultiJob():

            # cycle through each render layer and generate Job and Task arguments for each
            for layer_row in self.extended_widget.getLayerRows(checked=True):
                logger.debug("layer_row: %s", layer_row)

                # unpack data from layer
                layer_name = layer_row["layer_name"]
                instance_type = layer_row["instance_type"]["name"]
                preemptible = layer_row["preemptible"]

                job_args = self.getJobArgs(layer_names=(layer_name,))
                tasks_args = self.getTasksArgs(instance_type,
                                               preemptible,
                                               layer_names=(layer_name,))

                jobs_args.append((job_args, tasks_args))

        # SINGLE RENDER JOB
        else:
            job_args = self.getJobArgs(layer_names)
            instance_type = self.getInstanceType()["name"]
            preemptible = self.getPreemptibleCheckbox()
            tasks_args = self.getTasksArgs(instance_type, preemptible, layer_names=layer_names)
            jobs_args.append((job_args, tasks_args))

        return jobs_args

    def getJobArgs(self, layer_names):
        '''
        optional :label, type: String
        optional :metadataId, type: String
        optional :notification, type: Map do 
            optional :emails, type: String
            optional :slack, type: String
            exactly_one_of [:emails, :slack]
        end
        requires :projectId, type: String
        optional :title, type: String   
       '''

        job_args = {}

        # Notifications
        email_notification = self.getNotifications()
        if email_notification:
            job_args["notification"] = {"email": email_notification}

        job_args["project_id"] = self.getProject()["id"]
        job_args["title"] = self.getJobTitle(layer_names=layer_names, is_upload_job=self.isUploadOnly())
        return job_args

    def getTasksArgs(self, instance_type, preemptible, layer_names=()):
        '''
        Generate args per Task.  Any args that are the same across all the tasks
        can be passed in via common_args


        upload_id=upload_id, 
                                                metadata_id=metadata_id, 
                                                layer_names=layer_names,
                                                scout_frames=scout_frames,
                                                frames=frames)


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
        chunk_size = self.getChunkSize()
        environment = self.getEnvironment()
        frames = self.getFrames()
        location = self.getLocation()
        output_path = self.getOutputDir()
        project_id = self.getProject()["id"]
        software_package_ids = self.getSoftwarePackageIds()

        # Create a template command that be be used for each task's command
        cmd_template = "Render -s %s -e %s -b %s %s -rd /tmp/render_output/ %s"

        # Retrieve the source maya file
        maya_filepath = self.getSourceFilepath()
        # Strip the lettered drive from the filepath (if one exists).
        # This is a hack to allow a Windows filepath to be properly used
        # as an argument in a linux shell on the backend. Not pretty.
        maya_filepath_nodrive = os.path.splitdrive(maya_filepath)[-1]

        # dictate which render layer(s) to render
        render_layer_args = "-rl " + ",".join(layer_names)

        # -----------------
        # PER-TASK ARGS
        # ------------------
        # Use the task frames generator to dispense the appropriate amount of
        # frames per task, generating a command for each task to execute
        tasks_args = []
        frames_generator = submitter.TaskFramesGenerator(frames,
                                                         chunk_size,
                                                         uniform_chunk_step=True)
        for task_idx, cmd_args in enumerate(frames_generator):
            start_frame, end_frame, step, task_frames = cmd_args
            task_cmd = cmd_template % (start_frame,
                                       end_frame,
                                       step,
                                       render_layer_args,
                                       maya_filepath_nodrive)

            task_label = str(task_idx).zfill(3)
            # convert frames to flatten string
            frames_str = seqLister.condenseSeq(task_frames)
            assert len(frames_str) == 1, "Didn't get exactly 1 item  in frames list: %s" % frames_str
            task_args = {
                "command": task_cmd,
                "environment": environment,
                "frames": frames_str[0],
                "instance_type": instance_type,
                "label": task_label,
                "location": location,
                "output_path": output_path,
                "preemptible": preemptible,
                "project_id": project_id,
                "software_package_ids": software_package_ids,
            }

            tasks_args.append(task_args)
        return tasks_args

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
        Override the base class so that a validation pre-process can be run.  

        We also collect dependencies  at this point and pass that
        data along...
        In order to validate the submission, dependencies must be collected
        and inspected. Because we don't want to unnessarily collect dependencies
        again (after validation succeeds), we also pass the depenencies along
        in the returned dictionary.
        '''
        # Call the parent presubmission method
        super(MayaConductorSubmitter, self).runPreSubmission()

        # collect a list of paths to upload.
        raw_upload_paths = self.collectDependencies()

        # Add any paths that have been specified in the config file
        raw_upload_paths.extend(CONFIG.get("upload_paths") or [])

        # Get all files that we want to have integrity enforcement when uploading via the daemon
        enforced_md5s = self.getEnforcedMd5s() or {}

        # add md5 enforced files to dependencies. In theory these should already be included in the raw_dependencies, but let's cover our bases
        raw_upload_paths.extend(enforced_md5s.keys())

        # If the renderer is arnold and "use .tx files is enabled", then add corresponding tx files.
        # TODO:(lws) This process shouldn't happen here. We can't keep tacking on things for random
        # software-specific behavior. We're going to need start separating behavior via classes (perhaps
        # one for each renderer type?)
        if maya_utils.is_arnold_renderer() and maya_utils.is_arnold_tx_enabled():
            tx_filepaths = file_utils.get_tx_paths(raw_upload_paths, existing_only=True)
            raw_upload_paths.extend(tx_filepaths)

        error_message, validated_data = self.runValidation({"upload_paths": raw_upload_paths,
                                                            "checked_layers": self.extended_widget.getLayerRows(checked=True)})
        if error_message:
            pyside_utils.launch_error_box("Validation Error", error_message, parent=self)
            raise Exception(error_message)

        return {"upload_paths": validated_data.get("upload_paths") or [],
                "enforced_md5s": enforced_md5s}

    def getJobTitle(self, layer_names=(), is_upload_job=False):
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
        logger.debug("layer_names: %s", layer_names)

        maya_filepath = self.getSourceFilepath()
        _, maya_filename = os.path.split(maya_filepath)

        # Cross-reference all renderable renderlayers in the maya scene with
        # the renderlayers that the user has selected in the UI.  If there is
        # a 1:1 match, then don't list any render layers in the job title (as
        # it is assumed that all will be rendered).  If there is not a 1:1
        # match, then add the render layers to the title which the user has
        # selected in the UI

        all_renderable_layers = []
        for render_layer_info in maya_utils.get_render_layers_info():
            if render_layer_info['renderable']:
                all_renderable_layers.append(render_layer_info['layer_name'])

        # If all render layers are being rendered, then don't specify them in the job title
        if set(all_renderable_layers) == set(layer_names):
            render_layer_str = ""
        # Otherwise specify the user-selected layers in the job title
        else:
            render_layer_str = " - " + ", ".join(layer_names)

        title = "MAYA - %s%s" % (maya_filename, render_layer_str)
        if is_upload_job:
            title = "UPLOAD %s" % title
        return title

    def runValidation(self, validation_data):
        '''
        This is an added method (i.e. not a base class override), that allows
        validation to occur when a user presses the "Submit" button. If the
        validation fails, a notification dialog appears to the user, halting
        the submission process. 

        Validate that the data being submitted is...valid.

        1. Dependencies

        '''
        validated_data = {}

        # Check the validation data to find any paths that have an error message
        error_message = ""
        if not validation_data.get("checked_layers"):
            error_message += "No render layers have been check boxed!"

        # validate all of the dependendencies
        invalid_paths, processed_paths = file_utils.validate_paths(validation_data["upload_paths"])
        validated_data["upload_paths"] = processed_paths

        for error in invalid_paths.values():
            if error:
                error_message += "\n%s" % error

        return error_message, validated_data

    def getSourceFilepath(self):
        '''
        Return the currently opened maya file
        '''
        return maya_utils.get_maya_scene_filepath()

    def on_ui_upload_only_chkbx_toggled(self, toggled):
        '''
        This is connected by slot (see parent class)

        when the "Upload Only" checkbox is checked ON:
            - call the parent class's method
            - disable render layers section 
            - disable the render layer jobs checkob

        when the "Upload Only" checkbox is checked OFF, do the inverse...
        '''
        super(MayaConductorSubmitter, self).on_ui_upload_only_chkbx_toggled(toggled)
        self.extended_widget.ui_render_layers_trwgt.setDisabled(toggled)
        self.extended_widget.ui_layer_jobs_chkbx.setDisabled(toggled)

    def isMultiJob(self):
        '''
        Return
        '''
        return self.extended_widget.ui_layer_jobs_chkbx.isChecked()

    def on_ui_layer_jobs_chkbx_toggled(self, toggled):
        '''
        When the layer jobs checkbox is toggled enable/disable options that 
        conflict with that option
        '''
        if toggled:
            self.extended_widget.ui_render_layers_trwgt.restoreHeaderState()
        else:
            self.extended_widget.ui_render_layers_trwgt.saveHeaderState()

        # Hide the global instance type widget (instance type is implemented per render layer)
        self.ui_instance_wgt.setVisible(not toggled)

        # Toggle the Instance Type column  visibility
        instance_column_idx = self.extended_widget.ui_render_layers_trwgt.instance_cmbx_item_idx
        self.extended_widget.ui_render_layers_trwgt.setColumnHidden(instance_column_idx, not toggled)

        # Toggle the Preemptible column visibility
        preemptible_column_idx = self.extended_widget.ui_render_layers_trwgt.preemptible_chkbx_idx
        self.extended_widget.ui_render_layers_trwgt.setColumnHidden(preemptible_column_idx, not toggled)

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


class MayaRenderLayerTreeWidget(submitter.CheckBoxInstancesTreeWidget):

    icon_filepath_checked = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_on_greenx_8x7.png')
    icon_filepath_unchecked = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_off_redx_8x7.png')
    icon_filepath_checked_disabled = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_on_greenx_disabled_8x7.png')
    icon_filepath_unchecked_disabled = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_off_redx_disabled_8x7.png')

    # The index of the QTreeWidgetItem that contains the Instance Types QComboBox
    instance_cmbx_item_idx = 2

    # The index of the QTreeWidgetItem that contains the preemptible QCheckbox
    preemptible_chkbx_idx = 3

    def __init__(self, instance_types, parent=None):
        submitter.CheckBoxInstancesTreeWidget.__init__(self, instance_types, parent=parent)

    def initializeUi(self):
        super(MayaRenderLayerTreeWidget, self).initializeUi()
        self.setIndentation(0)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setHeaderItem(QtWidgets.QTreeWidgetItem(["Layer", "Camera", "Instance Type", "Preemptible"]))


def get_maya_window():
    '''
    Return the Qt instance of Maya's MainWindow
    '''
    mainWindowPtr = OpenMayaUI.MQtUtil.mainWindow()
    return wrapInstance(long(mainWindowPtr), QtWidgets.QMainWindow)
