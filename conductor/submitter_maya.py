
import os
import imp
import logging
from pprint import pformat
import sys
import uuid
from PySide import QtGui, QtCore
from shiboken import wrapInstance
from maya import OpenMayaUI

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conductor import CONFIG, submitter
from conductor.lib import maya_utils, pyside_utils, file_utils, api_client, common, loggeria, package_utils, conductor_submit

'''
TODO: 
1. When the Upload Only argument is sent to the conductor Submit object as True, does it ignore the filepath and render layer arguments?  Or should those arguments not be given to the Submit object.
3. Cull out unused maya dependencies.  Should we exclude materials that aren't assigned, etc?
5. Validate the maya file has been saved
'''

logger = logging.getLogger(__name__)


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

    def isRenderLayerJobs(self):
        '''
        Return
        '''
        return self.ui_layer_jobs_chkbx.isChecked()

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
                           "product":plugin_product,
                           "version":plugin_version,
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
        in the returned dictionary (so that we don't need to collect them again).
        '''
        # Call the parent presubmission method
        super(MayaConductorSubmitter, self).runPreSubmission()


        # collect a list of paths to upload.
        upload_paths = self.collectDependencies()

        # If uploading locally (i.e. not using  uploader daemon
        if self.getLocalUpload():
            # Don't need to enforce md5s for the daemon (don't want to do unnessary md5 hashing here)
            enforced_md5s = {}
        else:
            # Get all files that we want to have integrity enforcement when uploading via the daemon
            enforced_md5s = self.getEnforcedMd5s()

        # add md5 enforced files to dependencies. In theory these should already be included in the raw_dependencies, but let's cover our bases
        upload_paths.extend(enforced_md5s.keys())


        # If the renderer is arnold and "use .tx files is enabled", then add corresponding tx files.
        # TODO:(lws) This process shouldn't happen here. We can't keep tacking on things for random
        # software-specific behavior. We're going to need start seperating behavior via classes (perhaps
        # one for each renderer type?)
        if maya_utils.is_arnold_renderer() and maya_utils.is_arnold_tx_enabled():
            tx_filepaths = file_utils.get_tx_paths(upload_paths, existing_only=True)
            processed_tx_filepaths = file_utils.process_upload_filepaths(tx_filepaths)
            upload_paths.update(processed_tx_filepaths)

        # Validate the upload paths
        self.validateUploadPaths(upload_paths)


        return {"upload_paths":upload_paths,
                "enforced_md5s":enforced_md5s}



    def getUploadFiles(self, upload_paths, enforced_md5s):
        '''
        Parse/resolve all of the given upload paths (directories, path expressions
        files) to full filepaths.
        Generate a dictionary where the key is the filepath, and the value is
        the md5 of the file (or None if there is no md5 enforcement) 
        '''

        processed_filepaths = file_utils.process_upload_filepaths(upload_paths)

        # Convert the list of filepaths into a dictionary where all the values are None
        upload_files = dict([(path, None) for path in processed_filepaths])

        # process the enforced filepaths to ensure they exist/conform
        for md5, filepath in enforced_md5s.iteritems():
            processed_filepath = file_utils.process_upload_filepath(filepath)
            # this will always be a list. make sure that only one file is in this list
            # so that a single md5 value can corellate to it
            assert len(processed_filepath) == 1, "Found more than one file for path: %s\nGot: %s" % (filepath, processed_filepath)
            upload_files[processed_filepath[0]] = md5

        return upload_files



    def runSubmission_(self, pre_data):
        '''
        Submit one Job per render layer.  Each Job will use the same Upload object
        so uploading and syncing occurs only once.
        
        
        If the job is a local upload_job (meaning that the uploading will happen
        right now, as opposed to handled by a daemon later), then the status
        of the Upload should be set to invalid status.  Not until it's finished
        uploading, should the status be changed to "server/sync pending".
        If local_upload is False (meaning that the uploading will be handled
        later by a daemon), then set the status of the Upload to "client_pending"
        '''

        args = self.generateSubmissionArgs()

        project_id = "%s|%s" % (CONFIG["account"], args["project"])

        # Grab the file dependencies from data (note that this comes from the presubmission phase
        upload_files = self.getUploadFiles(upload_paths=pre_data.get("upload_paths") or [],
                                           enforced_md5s=pre_data.get("enforced_md5s") or {})

        metadata_id = None
        if args.get("metadata"):
            logger.info("Creating metadata...")
            logger.debug("metadata args\n: %s", pformat(args["metadata"]))
            metadata = api_client.MetadataResource.post(args["metadata"])
            logger.debug("metadata: %s", metadata)
            metadata_id = metadata['id']


        upload_id = None
        if upload_files:
            # If there are upload files provided, then create an Upload resource

            # Get the total bytes of all files that are part of the job
            logger.info("Calculating upload files size...")
            total_size = sum([os.stat(f).st_size for f in  upload_files.keys()])

            upload_args = {"location": args.get("location"),
                           "metadata": metadata_id,
                           "owner": args["owner"],
                           "project": project_id,
                           "status": conductor_submit.STATUS_UNINITIALIZED,
                           "metadata": metadata_id,
                           "total_size":total_size,
                           "upload_files": upload_files}

            logger.debug("upload_args\n: %s", pformat(upload_args))
            upload = api_client.UploadResource.post(upload_args)
            logger.debug("upload: %s", upload)
            upload_id = upload["id"]


        render_layers = self.extended_widget.getSelectedRenderLayers()

        job_args = {"chunk_size":   args.get("chunk_size"),
                    "docker_image": args.get("docker_image"),
                    "environment":  args.get("environment"),
                    "frame_padding":args.get("frame_padding"),
                    "frame_range":  args.get("frame_range"),
                    "instance_type":args.get("instance_type"),
                    "location":     args.get("location"),
                    "max_instances":args.get("max_instances"),
                    "metadata":     metadata_id,
                    "notify":       args.get("notify"),
                    "owner":        args.get("owner"),
                    "output_path":  args.get("output_path"),
                    "priority":     args.get("priority"),
                    "project":      project_id,
                    "scout_frames": args.get("scout_frames"),
                    "software_packages": args.get("software_packages"),
                    "upload":       upload_id}

        job_ids = []

        # Submit the first job

        if self.extended_widget.isRenderLayerJobs() and not self.upload_only:

            print " Submitting Render Layer Jobs"
            for render_layer in render_layers:
                logger.debug("render_layer: %s", render_layer)


                job_args["command"] = self.getCommand(render_layers=[render_layer])
                job_args["job_title"] = self.getJobTitle(render_layers=[render_layer])

                print " Submitting Render layer Job: "
                job = api_client.JobResource.post(job_args)
                logger.debug("job: %s", job)
                job_ids.append(job["id"])

        else:
            command = self.getCommand(render_layers=render_layers)
            logger.debug("command: %s", command)

            job_title = self.getJobTitle(render_layers=[render_layer])
            logger.debug("job_title: %s", job_title)

            args = cls.consume_args(inherit_config, **kwargs)
            submission = cls(**args)
            jobs_resources.append(submission.create_resources())


        if upload_id:
            if self.args.local_upload:
                job_status = "uploading"
            else:
                job_status = "upload_pending"
        else:
            logger.warning("No upload created for job")
            job_status = "pending"

        job_ids = [job_resources["job"]["id"] for job_resources in jobs_resources]

        return conductor_submit.Submission.initialize_jobs(job_ids, job_status)


    def generateSubmissionArgs(self):
        '''
        Return a dictionary which contains the necessary conductor argument names
        and their values.  This dictionary will ultimately be passed directly 
        into a conductor Submit object when instantiating/calling it.
        
        Generally, the majority of the values that one would populate this dictionary
        with would be found by quering this UI, e.g.from the "frames" section of ui.
           
        '''
        args = {}
        args["project"] = self.getProject()
        args["notify"] = self.getNotifications()
        args["local_upload"] = self.getLocalUpload()

        if self.getUploadOnly():
            args["upload_only"] = self.getUploadOnly()
        else:
            args["cores"] = self.getInstanceType()['cores']
            args["environment"] = self.getEnvironment()
            args["frames"] = self.getFrameRangeString()
            args["chunk_size"] = self.getChunkSize()
            args["machine_type"] = self.getInstanceType()['flavor']
            args["output_path"] = self.getOutputDir()
            args["scout_frames"] = self.getScoutFrames()
            args["software_package_ids"] = self.getSoftwarePackageIds()



        return args


    def getCommand(self, render_layers=()):
        '''
        Return the command string that Conductor will execute.

        
        example:
            "Render -rd /tmp/render_output/ <frame_args> -rl render_layer1_name,render_layer2_name maya_maya_filepath.ma"

        The <frame_args> portion of the command will have values substitited into
        into it by conductor (when the job is submitted).  These values will be
        dictated by the "frames" argument.
        '''
        base_cmd = "Render -rd /tmp/render_output/ <frame_args> %s %s"
        render_layer_args = "-rl " + ",".join(render_layers)
        maya_filepath = self.getSourceFilepath()

        # Strip the lettered drive from the filepath (if one exists).
        # This is a hack to allow a Windows filepath to be properly used
        # as an argument in a linux shell on the backend. Not pretty.
        maya_filepath_nodrive = os.path.splitdrive(maya_filepath)[-1]

        cmd = base_cmd % (render_layer_args, maya_filepath_nodrive)
        return cmd


    def getJobTitle(self, render_layers=()):
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
        logger.debug("render_layers: %s", render_layers)

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
        if set(all_renderable_layers) == set(render_layers):
            render_layer_str = ""
        # Otherwise specify the user-selected layers in the job title
        else:
            render_layer_str = " - " + ", ".join(render_layers)

        title = "MAYA - %s%s" % (maya_filename, render_layer_str)
        return title


    def validateUploadPaths(self, upload_paths):
        '''
        Validate the given paths to upload. If the validation fails, 
        launch a dialog box and raise an exception.

        '''

        validation = file_utils.validate_paths(upload_paths)

        # IF there are any error messages (stored in the dict values)
        if any(validation.values()):
            message = ""
            for _, error_message in validation.iteritems():
                if error_message:
                    message += "\n%s" % error_message

            pyside_utils.launch_error_box("Invalid file paths!", message, parent=self)
            raise Exception(message)


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
        self.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.setHeaderItem (QtGui.QTreeWidgetItem(["Layer", "Camera"]))


def get_maya_window():
    '''
    Return the Qt instance of Maya's MainWindow
    '''
    mainWindowPtr = OpenMayaUI.MQtUtil.mainWindow()
    return wrapInstance(long(mainWindowPtr), QtGui.QMainWindow)


