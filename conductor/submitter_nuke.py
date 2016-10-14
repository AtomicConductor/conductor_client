import imp
import logging
import os
import sys

from PySide import QtGui

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conductor import CONFIG, submitter
from conductor.lib import file_utils, nuke_utils, pyside_utils, common, package_utils, api_client, conductor_submit


logger = logging.getLogger(__name__)


class NukeWidget(QtGui.QWidget):

    # The .ui designer filepath
    _ui_filepath = os.path.join(submitter.RESOURCES_DIRPATH, 'nuke.ui')

    def __init__(self, parent=None):
        super(NukeWidget, self).__init__(parent=parent)
        pyside_utils.UiLoader.loadUi(self._ui_filepath, self)
        self.initializeUi()
        self.refreshUi()

    def initializeUi(self):
        # Create Views TreeWidget
        self.ui_views_trwgt = NukeViewsTreeWidget()
        views_layout = self.ui_views_grpbx.layout()
        views_layout.insertWidget(0, self.ui_views_trwgt)

        # Create the Write nodes TreeWidget
        mainwindow = self.window()
        self.ui_write_nodes_trwgt = NukeWriteNodesTreeWidget(mainwindow._instance_types)
        write_nodes_layout = self.ui_write_nodes_grpbx.layout()
        write_nodes_layout.insertWidget(0, self.ui_write_nodes_trwgt)

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

        # Order items by write nodes names alphabetically
        for write_node, is_selected in sorted(write_nodes.iteritems(), key=lambda data: data[0].lower()):
            tree_item = QtGui.QTreeWidgetItem(self.ui_write_nodes_trwgt)
            tree_item.setText(0, write_node)
            # Check/uncheck the checkbox depending on whether the user has the write node selected in nuke
            self.ui_write_nodes_trwgt.addTopLevelCheckboxInstanceItem(tree_item, is_checked=is_selected)

        self.ui_write_nodes_trwgt.resizeColumnToContents(0)

    def populateViews(self, views):
        '''
        Populate each view into the UI QTreeWidget.
        All views will be selected by default
        '''
        self.ui_views_trwgt.clear()
        assert isinstance(views, list), "views argument must be a list. Got %s" % type(views)
        for view in sorted(views, key=str.lower):
            tree_item = QtGui.QTreeWidgetItem([view])
            self.ui_views_trwgt.addTopLevelItem(tree_item)

            # Checkbox ON all views by default
            tree_item.setCheckState(self.ui_views_trwgt.checkbox_column_idx, pyside_utils.get_qt_check_flag(True))

        #  If there is only one view, disable this box...
        if len(views) == 1:
            self.ui_views_trwgt.setDisabled(True)
        else:
            self.ui_views_trwgt.setEnabled(True)

    def getWriteRows(self, checked=None, highlighted=None, names_only=False):
        '''
        Return a dictionary of the names of the write nodes the UI
        '''
        rows = []

        for item in self.ui_write_nodes_trwgt.getRowItems(checked=checked, highlighted=highlighted):
            if names_only:
                row = item.text(0)
            else:
                row = {"write_name": item.text(0),
                       "instance_type": self.ui_write_nodes_trwgt.getItemInstanceType(item),
                       "preemptible": self.ui_write_nodes_trwgt.getItemPreemptible(item)}
            rows.append(row)

        return rows

    def getViews(self, checked=None, highlighted=None):
        '''
         Return the names of the views that are the UI
        '''
        views = []

        for item in self.ui_views_trwgt.getRowItems(checked=checked, highlighted=highlighted):
            views.append(str(item.text(0)))

        return views

    def isWriteNodeJobs(self):
        '''
        Return
        '''
        return self.ui_write_node_jobs_chkbx.isChecked()


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

        # connect signals from extended widget
        self.extended_widget.ui_write_node_jobs_chkbx.toggled.connect(self.on_ui_write_node_jobs_chkbx_toggled)

        #  disable multijob submissions for now
        self.extended_widget.ui_write_node_jobs_chkbx.setChecked(False)
        self.extended_widget.ui_write_node_jobs_chkbx.hide()

    def applyDefaultSettings(self):
        super(NukeConductorSubmitter, self).applyDefaultSettings()
        start, end = nuke_utils.get_frame_range()
        self.setFrameRange(start, end)
        self.extended_widget.refreshUi()

    def getExtendedWidget(self):
        return NukeWidget(self)

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

        # Get all the write nodes that have been checkboxed ON by the user
        write_names = self.extended_widget.getWriteRows(checked=True, names_only=True)
        view_names = self.extended_widget.getViews(checked=True)

        # UPLOAD-ONLY JOB
        # If an upload_only job, the
        if self.isUploadOnly():
            job_args = self.getJobArgs(write_names)
            jobs_args.append((job_args, []))

        # MULTIPLE RENDER JOBS
        elif self.isMultiJob():

            # cycle through each write node and generate Job and Task arguments for each
            for write_row in self.extended_widget.getWriteRows(checked=True):
                logger.debug("write_rows: %s", write_row)

                # unpack data from write
                write_names = (write_row["write_name"], )

                job_args = self.getJobArgs(write_names=write_names)
                tasks_args = self.getTasksArgs(instance_type=write_row["instance_type"]["name"],
                                               preemptible=write_row["preemptible"],
                                               write_names=write_names,
                                               view_names=view_names)

                jobs_args.append((job_args, tasks_args))

        # SINGLE RENDER JOB
        else:
            job_args = self.getJobArgs(write_names)
            instance_type = self.getInstanceType()["name"]
            preemptible = self.getPreemptibleCheckbox()
            tasks_args = self.getTasksArgs(instance_type, preemptible, write_names=write_names, view_names=view_names)
            jobs_args.append((job_args, tasks_args))

        return jobs_args

    def getJobArgs(self, write_names):
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
        job_args["title"] = self.getJobTitle(write_names=write_names, is_upload_job=self.isUploadOnly())
        return job_args

    def getTasksArgs(self, instance_type, preemptible, write_names=(), view_names=()):
        '''
        Return a list of tasks data.  Each item in the list represents one
        task of work that will be created. Each task dictionary has the following
        keys:
            command: The command for the task to execute

            frames: [optional], helps to bind/display the relationship between a 
                     task and the frames that the task is operating on.  Because
                     a task can be any arbitrary command, the notion of "frames"
                     may not be relevant and can be left empty.

        Example(two tasks):

            # Task 0
            [{"command": "nuke-render --view main -X AFWrite.write_exr -F 1-1x1 /tmp/my_nuke_file.nk
              "frames": "1"},
            # Task 1
             {"command": "nuke-render --view main -X AFWrite.write_exr -F 10-20x2 /tmp/my_nuke_file.nk""
              "frames": "10-20x2"}]
        '''
        chunk_size = self.getChunkSize()
        environment = self.getEnvironment()
        frames = self.getFrames()
        location = self.getLocation()
        output_path, _ = self.getOutputDir()
        project_id = self.getProject()["id"]
        software_package_ids = self.getSoftwarePackageIds()

        # Create a template command that be be used for each task's command
        cmd_template = "nuke-render %s %s -F %s-%sx%s %s"

        write_args = " ".join(["-X %s" % write_name for write_name in write_names])
        view_args = "--view %s" % ",".join(view_names)
        nuke_scriptpath = self.getSourceFilepath()

        # Strip the lettered drive from the filepath (if one exists).
        # This is a hack to allow a Windows filepath to be properly used
        # as an argument in a linux shell command on the backend. Not pretty.
        nuke_filepath_nodrive = os.path.splitdrive(nuke_scriptpath)[-1]

        # -----------------
        # PER-TASK ARGS
        # ------------------
        # Use the task frames generator to dispense the appropriate amount of
        # frames per task, generating a command for each task to execute
        tasks_args = []
        frames_generator = submitter.TaskFramesGenerator(frames,
                                                         chunk_size=chunk_size,
                                                         uniform_chunk_step=True)
        for task_idx, cmd_args in enumerate(frames_generator):
            start_frame, end_frame, step, task_frames = cmd_args
            task_cmd = cmd_template % (view_args,
                                       write_args,
                                       start_frame,
                                       end_frame,
                                       step,
                                       nuke_filepath_nodrive)

            task_label = str(task_idx).zfill(3)

            task_args = {
                "command": task_cmd,
                "environment": environment,
                "frames": [str(f) for f in task_frames],  # convert to strings
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

    def collectDependencies(self, write_nodes, views):
        '''
        For the given write nodes, return a list of filepaths that these write
        nodes rely upon (external file dependencies)
        '''
        # Get all of the node types and attributes to query for external filepaths on
        resources = common.load_resources_file()

        # Get all of node types and their knobs to search for depencies on
        dependency_knobs = resources.get("nuke_dependency_knobs") or {}

        # Collect the dependencies for those write nodes
        dependencies = nuke_utils.collect_dependencies(write_nodes, views, dependency_knobs)

        # Add the open Nuke file to the dependencies list
        dependencies.append(self.getSourceFilepath())
        return dependencies

    def getOutputDir(self):
        '''
        Override the Parent's method (that uses the Ui's values), and instead...
        From the selected Write nodes (in the UI), query their output paths
        and derive common directory which they all share (somewhere in their
        directory tree).  Return a two-item tuple, containing the output path, and
        a list of the write node's output paths 
        '''
        write_paths = []
        for write_name in self.extended_widget.getWriteRows(checked=True, names_only=True):
            filepath = nuke_utils.get_write_node_filepath(write_name)
            if filepath:
                write_paths.append(filepath)

        output_path = file_utils.get_common_dirpath(write_paths)
        return output_path, write_paths

    def runPreSubmission(self):
        '''
        Override the base class so that a validation pre-process can be run.  

        Run some validation here...
        In order to validate the submission, dependencies must be collected
        and inspected. Because we don't want to unnecessarily collect dependencies
        again (after validation succeeds), we also pass the dependencies along
        in the returned dictionary.

        '''
        # Call the parent presubmission method (this will call base class validation, etc
        super(NukeConductorSubmitter, self).runPreSubmission()

        #  Get the applicable views
        views = self.extended_widget.getViews(checked=True)

        # Get the write nodes that have been checkboxed ON by the user (in the UI)
        write_names = self.extended_widget.getWriteRows(checked=True, names_only=True)

        # collect a list of paths to upload.
        raw_upload_paths = self.collectDependencies(write_names, views)

        # Add any paths that have been specified in the config file
        raw_upload_paths.extend(CONFIG.get("upload_paths") or [])

        # Get all files that we want to have integrity enforcement when uploading via the daemon
        enforced_md5s = self.getEnforcedMd5s() or {}

        # add md5 enforced files to dependencies. In theory these should already be included in the raw_dependencies, but let's cover our bases
        raw_upload_paths.extend(enforced_md5s.keys())

        # Validate and raise an exception if necessary
        error_message, validated_data = self.runValidation({"upload_paths": raw_upload_paths,
                                                            "write_nodes": write_names,
                                                            "output_path": self.getOutputDir(),
                                                            "views": views})
        if error_message:
            pyside_utils.launch_error_box("Validation Error", error_message, parent=self)
            raise Exception(error_message)

        return {"upload_paths": validated_data["upload_paths"],
                "enforced_md5s": enforced_md5s,
                "output_path": validated_data["output_path"]}

    def getJobTitle(self, write_names=(), is_upload_job=False):
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
        all_write_nodes = nuke_utils.get_all_write_nodes().keys()

        # If all write nodes are being rendered, then don't specify them in the job title
        if set(write_names) == set(all_write_nodes):
            write_node_str = ""
        # Otherwise specify the user-selected writes in the job title
        else:
            write_node_str = " - " + ", ".join(write_names)

        title = "NUKE - %s%s" % (nuke_filename, write_node_str)
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

        1. Write Nodes have been checkboxed/selected
        2. Views has been selected
        3. There is a common output directory among the write nodes
        '''
        validated_data = {}
        error_message = ""

        if not validation_data["write_nodes"]:
            error_message += "\nNo Write nodes selected for rendering!\nPlease select at least one Write node from the UI before pressing Submit"
            return error_message, validated_data

        if not validation_data["views"]:
            error_message += "\nNo Views have been selected for rendering!\nPlease select at least one view from the UI before pressing Submit"
            return error_message, validated_data

        # Validate that there is a common root path across all of the Write nodes' output paths
        output_path, write_paths = validation_data["output_path"]
        if not output_path:
            error_message += "\nNo common/shared output directory. All output files should share a common root!\n\nOutput files:\n    %s" % "\n   ".join(write_paths)
            return error_message, validated_data
        validated_data["output_path"] = output_path

        # validate all of the upload filepaths
        invalid_paths, processed_paths = file_utils.validate_paths(validation_data["upload_paths"])
        validated_data["upload_paths"] = processed_paths

        for error in invalid_paths.values():
            error_message += "\n%s" % error

        return error_message, validated_data

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

    def isMultiJob(self):
        '''
        Return True if the job submission should be a multijob submission
        '''
        return self.extended_widget.ui_write_node_jobs_chkbx.isChecked()

    def on_ui_write_node_jobs_chkbx_toggled(self, toggled):
        '''
        When the write jobs checkbox is toggled enable/disable options that 
        conflict with that option
        '''
        if toggled:
            self.extended_widget.ui_write_nodes_trwgt.restoreHeaderState()
        else:
            self.extended_widget.ui_write_nodes_trwgt.saveHeaderState()

        # Hide the global instance type widget (instance type is implemented per write node)
        self.ui_instance_wgt.setVisible(not toggled)

        # Toggle the Instance Type column  visibility
        instance_column_idx = self.extended_widget.ui_write_nodes_trwgt.instance_cmbx_item_idx
        self.extended_widget.ui_write_nodes_trwgt.setColumnHidden(instance_column_idx, not toggled)

        # Toggle the Preemptible column visibility
        preemptible_column_idx = self.extended_widget.ui_write_nodes_trwgt.preemptible_chkbx_idx
        self.extended_widget.ui_write_nodes_trwgt.setColumnHidden(preemptible_column_idx, not toggled)


class NukeViewsTreeWidget(pyside_utils.CheckBoxTreeWidget):

    icon_filepath_checked = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_nuke4.png')
    icon_filepath_unchecked = os.path.join(submitter.RESOURCES_DIRPATH, 'blank_x8.png')
    icon_filepath_checked_disabled = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_gray23_x32.png')
    icon_filepath_unchecked_disabled = os.path.join(submitter.RESOURCES_DIRPATH, 'blank_x8.png')

    def initializeUi(self):
        super(NukeViewsTreeWidget, self).initializeUi()
        self.setIndentation(0)
        self.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.setHeaderItem(QtGui.QTreeWidgetItem(["Views"]))


class NukeWriteNodesTreeWidget(submitter.CheckBoxInstancesTreeWidget):

    icon_filepath_checked = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_nuke4.png')
    icon_filepath_unchecked = os.path.join(submitter.RESOURCES_DIRPATH, 'blank_x8.png')
    icon_filepath_checked_disabled = os.path.join(submitter.RESOURCES_DIRPATH, 'checkbox_gray23_x32.png')
    icon_filepath_unchecked_disabled = os.path.join(submitter.RESOURCES_DIRPATH, 'blank_x8.png')

    # The index of the QTreeWidgetItem that contains the Instance Types QComboBox
    instance_cmbx_item_idx = 1

    # The index of the QTreeWidgetItem that contains the preemptible QCheckbox
    preemptible_chkbx_idx = 2

    def __init__(self, instance_types, parent=None):
        super(NukeWriteNodesTreeWidget, self).__init__(instance_types, parent=parent)

    def initializeUi(self):
        super(NukeWriteNodesTreeWidget, self).initializeUi()
        self.setIndentation(0)
        self.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.setHeaderItem(QtGui.QTreeWidgetItem(["Write Node", "Instance Type", "Preemptible"]))
