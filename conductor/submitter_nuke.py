import logging
import os
import sys
from PySide import QtGui, QtCore
import nuke
import imp

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from conductor import CONFIG, submitter
from conductor.lib import file_utils, nuke_utils, pyside_utils, common, api_client, loggeria

logger = logging.getLogger(__name__)

'''
TODO:
1. implement pyside inheritance for Nuke's window interface
2. Validate that at least one write node is selected
3. Test file pathing on Windows. Especially file_utils manipulations.
'''

class NukeWidget(QtGui.QWidget):

    # The .ui designer filepath
    _ui_filepath = os.path.join(submitter.RESOURCES_DIRPATH, 'nuke.ui')

    def __init__(self, parent=None):
        super(NukeWidget, self).__init__(parent=parent)
        pyside_utils.UiLoader.loadUi(self._ui_filepath, self)
        self.refreshUi()

    def refreshUi(self):
        write_nodes = nuke_utils.get_all_write_nodes()
        self.populateWriteNodes(write_nodes)


    def populateWriteNodes(self, write_nodes):
        '''
        Populate each Write and Deep Write node into the UI QTreeWidget.
        Any write nodes that are currently selected in nuke by the user will be
        also be selected in UI. Note that only write nodes that are selected in 
        the UI will be rendered when submitting to Conductor.
        '''
        self.ui_write_nodes_trwgt.clear()
        assert isinstance(write_nodes, dict), "write_nodes argument must be a dict. Got: %s" % type(write_nodes)
        for write_node, selected in write_nodes.iteritems():
            tree_item = QtGui.QTreeWidgetItem([write_node])
            self.ui_write_nodes_trwgt.addTopLevelItem(tree_item)

            # If the node is selected in Nuke, then select it in the UI
            if selected:
                self.ui_write_nodes_trwgt.setItemSelected(tree_item, True)


    def getSelectedWriteNodes(self):
        '''
        Return the names of the write nodes that are selected in the UI
        '''
        return [str(item.text(0)) for item in self.ui_write_nodes_trwgt.selectedItems()]

    def getUploadOnlyBool(self):
        '''
        Return whether the "Upload Only" checkbox is checked on or off.
        '''
        return self.ui_upload_only.isChecked()


    @QtCore.Slot(bool, name="on_ui_upload_only_toggled")
    def on_ui_upload_only_toggled(self, toggled):
        '''
        when the "Upload Only" checkbox is checked on, disable the Write 
        Nodes widget. when the "Upload Only" checkbox is checked off, enable
        the Write Nodes widget.
        '''
        self.ui_write_nodes_trwgt.setDisabled(toggled)




class NukeConductorSubmitter(submitter.ConductorSubmitter):
    '''
    The class is PySide front-end for submitting Nuke renders to Conductor.
    To launch the UI, simply call self.runUI method.
    
    This class serves as an implemenation example of how one might write a front 
    end for a Conductor submitter for Nuke.  This class is designed to be ripped
    apart of subclassed to suit the specific needs of a studio's pipeline. 
    Have fun :) 
    '''

    _window_title = "Conductor - Nuke"


    @classmethod
    def runUi(cls):
        '''
        Launch the UI
        '''
        ui = cls()
        ui.show()

    def __init__(self, parent=None):
        super(NukeConductorSubmitter, self).__init__(parent=parent)
        self.refreshUi()
        self.loadUserSettings()

    def initializeUi(self):
        super(NukeConductorSubmitter, self).initializeUi()
        # Hide the output path widget.  Not sure if this is safe to expose yet.  I don't think it will work for nuke.
        self.ui_output_path_widget.hide()

    def refreshUi(self):
        start, end = nuke_utils.get_frame_range()
        self.setFrameRange(start, end)
        self.extended_widget.refreshUi()

    def getExtendedWidget(self):
        return NukeWidget()


    def generateConductorCmd(self):
        '''
        Return the command string that Conductor will execute
        
        example:
            "-X AFWrite.write_exr -F %f /Volumes/af/show/walk/shots/114/114_100/sandbox/mjtang/tractor/nuke_render_job_122/walk_114_100_main_comp_v136.nk"

        '''
        base_cmd = "-F %%f %s %s"

        write_nodes = self.extended_widget.getSelectedWriteNodes()
        write_nodes_args = ["-X %s" % write_node for write_node in write_nodes]
        nuke_scriptpath = self.getSourceFilepath()
        cmd = base_cmd % (" ".join(write_nodes_args), nuke_scriptpath)
        return cmd


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

        write_nodes = self.extended_widget.getSelectedWriteNodes()
        dependencies = nuke_utils.collect_dependencies(write_nodes, dependency_knobs)
        dependencies.append(self.getSourceFilepath())
        return dependencies


    def getOutputPath(self):
        '''
        From the selected Write nodes (in the UI), query their output paths
        and derive common directory which they all share (somewhere in their
        directory tree).  Return a two-item tuple, containing the output path, and
        a list of the write node's output paths 
        '''
        write_paths = []
        write_nodes = self.extended_widget.getSelectedWriteNodes()

        for write_node in write_nodes:
            filepath = nuke_utils.get_write_node_filepath(write_node)
            if filepath:
                write_paths.append(filepath)

        output_path = file_utils.get_common_dirpath(write_paths)
        return output_path, write_paths

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

        # If uploading locally (i.e. not using  uploader daemon
        if self.getLocalUpload():
            # Don't need to enforce md5s for the daemon (don't want to do unnessary md5 hashing here)
            enforced_md5s = {}
        else:
            # Get all files that we want to have integrity enforcement when uploading via the daemon
            enforced_md5s = self.getEnforcedMd5s()

        # add md5 enforced files to dependencies. In theory these should already be included in the raw_dependencies, but let's cover our bases
        raw_dependencies.extend(enforced_md5s.keys())


        dependencies = file_utils.process_dependencies(raw_dependencies)
        output_path, write_paths = self.getOutputPath()
        raw_data = {"dependencies":dependencies,
                    "output_path":[output_path, write_paths]}

        is_valid = self.runValidation(raw_data)
        return {"abort":not is_valid,
                "dependencies":dependencies,
                "output_path":output_path,
                "enforced_md5s":enforced_md5s}


    def getDockerImage(self):
        '''
        If there is a docker image in the config.yml file, then use it (the
        parent class' method retrieves this).  Otherwise query Nuke and its
        plugins for their version information, and then query  Conductor for 
        a docker image that meets those requirements. 
        '''
        docker_image = super(NukeConductorSubmitter, self).getDockerImage()
        if not docker_image:
            nuke_version = nuke_utils.get_nuke_version()
            software_info = {"software": "nuke",
                             "software_version":nuke_version}

            # Get a list of nuke plugins
            plugins = nuke_utils.get_plugins()
            # Convert the plugins list into a dictionary (to conform to endpoint expectations)
            # Populate the keys with each plugin, where the value is an empty string
            # (hopefully we will populate it with relevant information such as plugin version, etc)
            plugins_dict = dict([(p, "") for p in plugins])
            software_info["plugins"] = plugins_dict
            docker_image = common.retry(lambda: api_client.request_docker_image(software_info))
        return docker_image

    def getJobTitle(self):
        '''
        Generate and return the title to be given to the job.  This is the title
        that will be displayed in the webUI.
                
        Construct the job title by using the software name (Nuke), followed by
        the filename of nuke file (excluding directory path), followed by the
        write nodes being rendered.  If all of the write nodes in the nuke 
        file are being rendered then don't list any of them. 
        
        Nuke - <nuke scriptname> - <writenodes> 
        
        example: "Nuke - my_nuke_script.nk - beauty, shadow, spec"
        '''
        nuke_filepath = self.getSourceFilepath()
        _, nuke_filename = os.path.split(nuke_filepath)

        # Cross-reference all write nodes in the nuke script with
        # the write nodes that the user has selected in the UI.  If there is
        # a 1:1 match, then don't list any write nodes in the job title (as
        # it is assumed that all will be rendered).  If there is not a 1:1
        # match, then add the write nodes to the title which the user has
        # selected in the UI
        selected_write_nodes = self.extended_widget.getSelectedWriteNodes()
        all_write_nodes = nuke_utils.get_all_write_nodes().keys()

        # If all write nodes are being rendered, then don't specify them in the job title
        if set(selected_write_nodes) == set(all_write_nodes):
            write_node_str = ""
        # Otherwise specify the user-selected layers in the job title
        else:
            write_node_str = " - " + ", ".join(selected_write_nodes)

        title = "NUKE - %s%s" % (nuke_filename, write_node_str)
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


        # ## Validate that there is a common root path across all of the Write
        # nodes' output paths
        output_path, write_paths = raw_data["output_path"]
        if not output_path:
            message = "No common/shared output directory. All output files should share a common root!\n\nOutput files:\n    %s" % "\n   ".join(write_paths)
            pyside_utils.launch_error_box("No common output directory!", message, parent=self)
            raise Exception(message)

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
            upload_file: str , the filepath to the dependency text file 
            upload_only: bool
            upload_paths: list of str?
            usr: str
        '''
        conductor_args = {}
        conductor_args["cmd"] = self.generateConductorCmd()
        conductor_args["cores"] = self.getInstanceType()['cores']
        conductor_args["env"] = self.getEnvironment()
        conductor_args["job_title"] = self.getJobTitle()
        conductor_args["machine_type"] = self.getInstanceType()['flavor']
        # Grab the enforced md5s files from data (note that this comes from the presubmission phase
        conductor_args["enforced_md5s"] = data.get("enforced_md5s") or {}
        conductor_args["force"] = self.getForceUploadBool()
        conductor_args["frames"] = self.getFrameRangeString()
        conductor_args["docker_image"] = self.getDockerImage()
        conductor_args["local_upload"] = self.getLocalUpload()
        conductor_args["notify"] = self.getNotifications()
        conductor_args["output_path"] = data["output_path"]
        conductor_args["resource"] = self.getResource()
        conductor_args["upload_only"] = self.extended_widget.getUploadOnlyBool()
        # Grab the file dependencies from data (note that this comes from the presubmission phase
        conductor_args["upload_paths"] = (data.get("dependencies") or {}).keys()

        return conductor_args


    def runConductorSubmission(self, data):

        # If an "abort" key has a True value then abort submission
        if data.get("abort"):
            logger.warning("Conductor: Submission aborted")
            return data

        return super(NukeConductorSubmitter, self).runConductorSubmission(data)

    def getSourceFilepath(self):
        '''
        Return the currently opened nuke script
        '''
        return nuke_utils.get_nuke_script_filepath()
