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
from conductor.lib import file_utils, nuke_utils, pyside_utils, common, package_utils

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
        views = nuke_utils.get_views()
        self.populateWriteNodes(write_nodes)
        self.populateViews(views)

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

    def populateViews(self, views):
        '''
        Populate each view into the UI QTreeWidget.
        All views will be selected by default
        '''
        self.ui_views_trwgt.clear()
        assert isinstance(views, list), "views argument must be a list. Got %s" % type(views)
        for view in views:
            tree_item = QtGui.QTreeWidgetItem([view])
            self.ui_views_trwgt.addTopLevelItem(tree_item)
            self.ui_views_trwgt.setItemSelected(tree_item, True)

        #  If there is only one view, disable this box...
        if len(views) == 1:
            self.ui_views_trwgt.setDisabled(True)
        else:
            self.ui_views_trwgt.setEnabled(True)


    def getSelectedWriteNodes(self):
        '''
        Return the names of the write nodes that are selected in the UI
        '''
        return [str(item.text(0)) for item in self.ui_write_nodes_trwgt.selectedItems()]

    def getSelectedViews(self):
        '''
        Return the names of the views that are selected in the UI
        '''
        return [str(item.text(0)) for item in self.ui_views_trwgt.selectedItems()]

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

    product = "nuke"

    def __init__(self, parent=None):
        super(NukeConductorSubmitter, self).__init__(parent=parent)

    def createUI(self):
        super(NukeConductorSubmitter, self).createUI()
        # Hide the output path widget.  Not sure if this is safe to expose yet.  I don't think it will work for nuke.
        self.ui_output_path_widget.hide()

    def applyDefaultSettings(self):
        super(NukeConductorSubmitter, self).applyDefaultSettings()
        start, end = nuke_utils.get_frame_range()
        self.setFrameRange(start, end)
        self.extended_widget.refreshUi()

    def getExtendedWidget(self):
        return NukeWidget()


    def getCommand(self):
        '''
        Return the command string that Conductor will execute
        
        example:
            "-X AFWrite.write_exr <frame_args> /Volumes/af/show/walk/shots/114/114_100/sandbox/mjtang/tractor/nuke_render_job_122/walk_114_100_main_comp_v136.nk"

        The <frame_args> portion of the command will have values substitited into
        into it by conductor (when the job is submitted).  These values will be
        dictated by the "frames" argument.
        '''
        base_cmd = "nuke-render <frame_args> %s %s %s"

        write_nodes = self.extended_widget.getSelectedWriteNodes()
        write_nodes_args = ["-X %s" % write_node for write_node in write_nodes]
        selected_views = self.extended_widget.getSelectedViews()
        view_args = "--view %s" % ",".join(selected_views)
        nuke_scriptpath = self.getSourceFilepath()

        # Strip the lettered drive from the filepath (if one exists).
        # This is a hack to allow a Windows filepath to be properly used
        # as an argument in a linux shell command on the backend. Not pretty.
        nuke_filepath_nodrive = os.path.splitdrive(nuke_scriptpath)[-1]

        cmd = base_cmd % (" ".join(write_nodes_args), view_args, nuke_filepath_nodrive)
        return cmd


    def collectDependencies(self, write_nodes, views):
        '''
        For the given write nodes, return a list of filepaths that these write
        nodes rely upon (external file dependencies)
        '''
        # Get all of the node types and attributes to query for external filepaths on
        resources = common.load_resources_file()

        # Get all of node types and their knobs to search for depencies on
        dependency_knobs = resources.get("nuke_dependency_knobs") or {}

        # Collecte the depenecies for those write nodes
        dependencies = nuke_utils.collect_dependencies(write_nodes, views, dependency_knobs)

        # Add the open nuke file to the depencies list
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

        # Get the write nodes that have been selected by the user (in the UI)
        write_nodes = self.extended_widget.getSelectedWriteNodes()

        if not write_nodes:
            message = "No Write nodes selected for rendering!\nPlease select at least one Write node from the UI before pressing Submit"
            pyside_utils.launch_error_box("No Write nodes selected!", message, parent=self)
            raise Exception(message)

        #  Get the applicable views
        views = self.extended_widget.getSelectedViews()
        if not views:
            message = "No views selected for rendering!\nPlease select at least one view from the UI before pressing Submit"
            pyside_utils.launch_error_box("No views selected!", message, parent=self)
            raise Exception(message)

        raw_dependencies = self.collectDependencies(write_nodes, views)

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

        # IF there are any error messages (stored in the dict values)
        if any(dependencies.values()):
            message = ""
            for _, error_message in dependencies.iteritems():
                if error_message:
                    message += "\n%s" % error_message

            pyside_utils.launch_error_box("Invalid file paths!", message, parent=self)
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
        are specific for Nuke.  See the base class' docstring for more details.
        '''

        # Get the core arguments from the UI via the parent's  method
        conductor_args = super(NukeConductorSubmitter, self).generateConductorArgs(data)

        # Grab the enforced md5s files from data (note that this comes from the presubmission phase
        conductor_args["enforced_md5s"] = data.get("enforced_md5s") or {}

        # Grab the file dependencies from data (note that this comes from the presubmission phase
        conductor_args["upload_paths"] = (data.get("dependencies") or {}).keys()

        # the output path gets dynamically generated based upon which write nodes the user has selected
        conductor_args["output_path"] = data["output_path"]

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

    # THIS IS COMMENTED OUT UNTIL WE DO DYNAMIC PACKAGE LOOKUP
#     def getHostProductInfo(self):
#         return nuke_utils.NukeInfo.get()
    # THIS IS COMMENTED OUT UNTIL WE DO DYNAMIC PACKAGE LOOKUP
#     def getPluginsProductInfo(self):
#         return nuke_utils.get_plugins_info()



    def getHostProductInfo(self):
        host_version = nuke_utils.NukeInfo.get_version()
        package_id = package_utils.get_host_package(self.product, host_version, strict=False).get("package")
        host_info = {"product": self.product,
                     "version": host_version,
                     "package_id": package_id}
        return host_info

    def getPluginsProductInfo(self):
        return nuke_utils.get_plugins_info()
