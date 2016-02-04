
import os
import imp
import logging
import traceback
import sys
import uuid

# from PySide import QtGui, QtCore
# from shiboken import wrapInstance


try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from conductor import CONFIG, submitter
from conductor import CONFIG

# from conductor.lib import katana_utils, pyside_utils, file_utils, api_client, common, loggeria
from conductor.lib import katana_utils, file_utils, api_client, common, loggeria, conductor_submit



logger = logging.getLogger(__name__)

# class MayaWidget(QtGui.QWidget):
#
#     # The .ui designer filepath
#     _ui_filepath = os.path.join(submitter.RESOURCES_DIRPATH, 'maya.ui')
#
#     def __init__(self, parent=None):
#         super(MayaWidget, self).__init__(parent=parent)
#         pyside_utils.UiLoader.loadUi(self._ui_filepath, self)
#         self.initializeUi()
#         self.refreshUi()
#
#     def initializeUi(self):
#         self.ui_render_layers_trwgt = MayaCheckBoxTreeWidget()
#         treewgt_layout = self.ui_render_layers_grpbx.layout()
#         treewgt_layout.insertWidget(0, self.ui_render_layers_trwgt)
#
#
#     def refreshUi(self):
#         render_layers_info = maya_utils.get_render_layers_info()
#         self.populateRenderLayers(render_layers_info)
#
#
#     def populateRenderLayers(self, render_layers_info):
#         '''
#         Populate each render layer into the UI QTreeWidget.
#         If the render layer has been set to renderable in maya, then check its
#         qtreewidgetitem's checkbox (on) the the render layer  UI.  Only render
#         layers that are checked on will be rendered
#         '''
#         self.ui_render_layers_trwgt.clear()
#         assert isinstance(render_layers_info, list), "render_layers argument must be a list. Got: %s" % type(render_layers_info)
#         for render_layer_info in reversed(render_layers_info):
#             tree_item = QtGui.QTreeWidgetItem([render_layer_info["layer_name"],
#                                                render_layer_info["camera_shortname"]])
#
#             tree_item.setFlags(tree_item.flags() | QtCore.Qt.ItemIsUserCheckable)
#             tree_item._camera_transform = render_layer_info["camera_transform"]
#             self.ui_render_layers_trwgt.addTopLevelItem(tree_item)
#
#             # If the render layer is set to renderable, then check the item's checkbox on
#             if render_layer_info["renderable"]:
#                 tree_item.setCheckState(0, QtCore.Qt.Checked)
#             else:
#                 tree_item.setCheckState(0, QtCore.Qt.Unchecked)
#
#
#         self.ui_render_layers_trwgt.resizeColumnToContents(0)
#
#     def getSelectedRenderLayers(self):
#         '''
#         Return the names of the render layers that have their checkboxes checked on
#         '''
#         selected_layers = []
#         for row_idx in range(self.ui_render_layers_trwgt.topLevelItemCount()):
#             item = self.ui_render_layers_trwgt.topLevelItem(row_idx)
#             if item.checkState(0) == QtCore.Qt.Checked:
#                 selected_layers.append(item.text(0))
#         return selected_layers
#
#
#     def getUploadOnlyBool(self):
#         '''
#         Return whether the "Upload Only" checkbox is checked on or off.
#         '''
#         return self.ui_upload_only.isChecked()
#
#
#     @QtCore.Slot(bool, name="on_ui_upload_only_toggled")
#     def on_ui_upload_only_toggled(self, toggled):
#         '''
#         when the "Upload Only" checkbox is checked on, disable the Render
#         Layers widget. when the "Upload Only" checkbox is checked off, enable
#         the Render Layers widget.
#         '''
#         self.ui_render_layers_trwgt.setDisabled(toggled)


class KatanaConductorSubmitter(object):
# class KatanaConductorSubmitter(submitter.ConductorSubmitter):
    '''
    
    This class inherits from the generic conductor submitter and adds an additional
    widget for maya-specific data.
    
    Note that the addional widget is stored (and accessible) via the 
    self.extended_widget attribute
    
    When the UI loads it will automatically populate various information:
        1. Frame range  
        2. Render layers (with their camera)
    
    '''


    _window_title = "Conductor - Katana"

    @classmethod
    def runUi(cls):
        '''
        Load the UI
        '''
        ui = cls()
        ui.show()

#     def __init__(self, parent=None):
# #         super(KatanaConductorSubmitter, self).__init__(parent=parent)
#         pass

#     def initializeUi(self):
#         super(KatanaConductorSubmitter, self).initializeUi()

#         if not self.ui_output_path_lnedt.text():
#             self.ui_output_path_lnedt.setText(katana_utils.get_output_dirpath())


#     def refreshUi(self):
#
#         start, end = maya_utils.get_frame_range()[0]
#         self.setFrameRange(start, end)
#         self.extended_widget.refreshUi()
#         self.ui_output_path_lnedt.setText(maya_utils.get_image_dirpath())


#     def getExtendedWidget(self):
#         return KatanaWidget()

#     def generateConductorCmd(self):
#         '''
#         Return the command string that Conductor will execute
#
#         example:
#             "-rd /tmp/render_output/ -s %f -e %f -rl render_layer1_name,render_layer2_name maya_maya_filepath.ma"
#         '''
#         base_cmd = "-rd /tmp/render_output/ -s %%f -e %%f %s %s"
#         render_layers = self.extended_widget.getSelectedRenderLayers()
#         render_layer_args = "-rl " + ",".join(render_layers)
#         maya_filepath = maya_utils.get_maya_scene_filepath()
#         cmd = base_cmd % (render_layer_args, maya_filepath)
#         return cmd


    def generateConductorCmd(self, source_filepath, render_node, render_internal_dependences=True):
        base_cmd = "katana --batch  -t %%f-%%f %s %s %s"

        arg_render_internal_dependences = "--render-internal-dependencies" if render_internal_dependences else ""
        arg_render_node = "--render-node=%s" % render_node.getName()
        arg_katana_file = "--katana-file=%s" % source_filepath

        cmd = base_cmd % (arg_render_internal_dependences, arg_render_node, arg_katana_file)

        return cmd


    def collectDependencies(self, katana_filepath, render_node):
        final_paths = []

        dep_paths = katana_utils.collect_dependencies(katana_filepath, render_node)
        for path in file_utils.process_upload_filepaths(dep_paths, strict=False):


            if not os.path.exists(path):
                logger.warning("1Path does not exist: %s", path)
                continue
            final_paths.append(path)

        return final_paths


    def getLocalUpload(self):
        return False


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


#     def getDockerImage(self):
#         '''
#         If there is a docker image in the config.yml file, then use it (the
#         parent class' method retrieves this).  Otherwise query Maya and its
#         plugins for their version information, and then query  Conductor for
#         a docker image that meets those requirements.
#         '''
#         docker_image = super(KatanaConductorSubmitter, self).getDockerImage()
#         if not docker_image:
#             maya_version = maya_utils.get_maya_version()
#             software_info = {"software": "maya",
#                              "software_version":maya_version}
#             plugin_versions = maya_utils.get_plugin_versions()
#             software_info["plugins"] = plugin_versions
#             docker_image = common.retry(lambda: api_client.request_docker_image(software_info))
#
#         return docker_image

    def getDockerImage(self):
        return ""

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
#             pyside_utils.launch_error_box("Invalid filepaths!", message, parent=self)
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
#         conductor_args["cores"] = self.getInstanceType()['cores']
        conductor_args["cores"] = self.getCores()
        conductor_args["job_title"] = self.getJobTitle(katana_filepath, render_node)
        conductor_args["machine_type"] = self.getMachineType()
#         conductor_args["machine_type"] = self.getInstanceType()['flavor']
        # Grab the enforced md5s files from data (note that this comes from the presubmission phase
#         conductor_args["enforced_md5s"] = data.get("enforced_md5s") or {}
#         conductor_args["force"] = self.getForceUploadBool()
        conductor_args["frames"] = self.getFrameRangeString()
        conductor_args["docker_image"] = self.getDockerImage()
        conductor_args["local_upload"] = self.getLocalUpload()
#         conductor_args["notify"] = self.ui_notify_lnedt.text()
        conductor_args["output_path"] = katana_utils.get_output_dirpath(render_node)
#         conductor_args["output_path"] = self.ui_output_path_lnedt.text()
#         conductor_args["resource"] = self.getResource()
        conductor_args["env"] = self.getEnvironment()
        # Grab the file dependencies from data (note that this comes from the presubmission phase
#         conductor_args["upload_paths"] = (data.get("dependencies") or {}).keys()
        conductor_args["upload_paths"] = (data.get("dependencies") or {}).keys()

        return conductor_args


#     def runConductorSubmission(self, data):
#
#         # If an "abort" key has a True value then abort submission
#         if data.get("abort"):
#             logger.warning("Conductor: Submission aborted")
#             return data
#
#         return super(KatanaConductorSubmitter, self).runConductorSubmission(data)



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




#     @pyside_utils.wait_cursor
#     @pyside_utils.wait_message("Conductor", "Submitting Conductor Job...")
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
#             pyside_utils.launch_error_box(title, message, self)
            logger.error(message)
            raise

        return response_code, response


    @classmethod
    def run(cls):
        logging.basicConfig(level=logging.DEBUG)
        submitter = cls()
        data = submitter.runPreSubmission()
        return submitter.runConductorSubmission(data)

#



    def getFrameRangeString(self):
        return "1035-1035x1"
#         return "1001-1064x1"


    def getCores(self):
        return 32

    def getMachineType(self):
        return "standard"

# class MayaCheckBoxTreeWidget(pyside_utils.CheckBoxTreeWidget):
#
#     icon_filepath_checked = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_on_greenx_8x7.png')
#     icon_filepath_unchecked = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_off_redx_8x7.png')
#     icon_filepath_checked_disabled = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_on_greenx_disabled_8x7.png')
#     icon_filepath_unchecked_disabled = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_off_redx_disabled_8x7.png')
#
#     def __init__(self, parent=None):
#         super(MayaCheckBoxTreeWidget, self).__init__(parent=parent)
#
#
#     def initializeUi(self):
#         super(MayaCheckBoxTreeWidget, self).initializeUi()
#         self.setIndentation(0)
#         self.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
#         self.setHeaderItem (QtGui.QTreeWidgetItem(["Layer", "Camera"]))
#
#
# def get_maya_window():
#     '''
#     Return the Qt instance of Maya's MainWindow
#     '''
#     mainWindowPtr = OpenMayaUI.MQtUtil.mainWindow()
#     return wrapInstance(long(mainWindowPtr), QtGui.QMainWindow)
#

