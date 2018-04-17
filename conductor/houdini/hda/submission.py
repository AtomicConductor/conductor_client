"""Build an object to represent a Conductor submission."""

import datetime
import hou
from conductor.houdini.hda import notifications_ui, types
from conductor.houdini.hda.job import Job
from conductor.houdini.lib import data_block


class Submission(object):
    """class Submission holds all data needed for a submission.

    A Submission contains many Jobs, and those Jobs contain
    many Tasks. A Submission can provide the correct args to
    send to Coductor, or it can be used to create a dry run
    to show the user what will happen. A Submission also
    manages a list of environment tokens that the user can
    access as $ variables, similar to Houdini Local
    variables, in order to build strings in the UI such as
    commands and job titles.
    """

    def __init__(self, node):
        """Collect member data from the Houdini UI.

        If the submission has been instantiated from a
        conductor::job node, then the submission data will
        be pulled from the submission tab, and the same node
        will be used as the only Job. Both self._node and
        self._jobs will point to the same node. If instead
        it is instantiated from a conductor::submitter
        node, then it will provide top level submission data
        and the Jobs (self._jobs) will built from the
        conductor::submitter's input nodes.

        * Generate a timestamp which will be common to all jobs.
        * Get the basename of the file in case its needed as a token.
        * Scene name - see notes on scene name in the Job.
        * Get upload flags and notification data.
        * Get the project.

        After _setenv has been called, the Submission level token
        variables are valid and calls to eval string attributes will
        correctly resolve where those tokens have been used.  This is
        why we eval jobs after the call to _setenv()
        """
        self._node = node
        if types.is_job_node(self._node):
            self._nodes = [node]
        else:
            self._nodes = node.inputs()

        self._use_timestamped_scene = bool(
            self._node.parm("use_timestamped_scene").eval())

        self._timestamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        hou.putenv("CT_TIMESTAMP", self._timestamp)
        self._scene = self._node.parm("scene_file").eval()

        self._upload = {
            "local": bool(self._node.parm("local_upload").eval()),
            "force": bool(self._node.parm("force_upload").eval()),
            "only": bool(self._node.parm("upload_only").eval())
        }

        self._project = self._get_project()

        self._tokens = self._setenv()

        self._notifications = notifications_ui.get_notifications(self._node)

        self._jobs = []
        for node in self._nodes:
            job = Job.create(node, self._tokens, self._scene)
            self._jobs.append(job)

    def _get_project(self):
        """Get the project name by looking up its ID.

        In case the current project is no longer in the list
        of projects, throw an error.
        """
        project_id = self._node.parm('project').eval()
        projects = data_block.for_houdini().projects()
        project_names = [project["name"]
                         for project in projects if project['id'] == project_id]
        if not project_names:
            raise hou.InvalidInput(
                "%s %s is an invalid project." %
                self._node.name(), project_id)
        return {
            "id": project_id,
            "name": project_names[0]
        }

    def _setenv(self):
        """Env tokens are variables to help the user build strings.

        The user interface has fields for strings such as
        job title, task command, metadata. The user can use
        these tokens, prefixed with a $ symbol, to build
        those strings. Tokens at the Submission level are
        also available in Job level fields, and likewise
        tokens at the Job level are available in Task level
        fields. However, it makes no sense the other way,
        for example you can't use a chunk token (available
        at Task level) in a Job title because a chunk
        changes for every task.

        We use hou.putenv() which basically sets these as
        global env vars in the scene. Unfortunately thats the
        only way because you can only attach variables local
        to nodes through the Houdini devkit.

        Once tokens are set, strings using them are expanded
        correctly. In fact we don't need these tokens to be
        stored on the Submission object (or Job or Task) for
        the submission to succeed. The only reason we store
        them is to display them in a dry-run scenario.
        """
        tokens = {}
        tokens["CT_TIMESTAMP"] = self._timestamp
        tokens["CT_SUBMITTER"] = self._node.name()
        # tokens["CT_HIPBASE"] = self._file["hipbase"]
        tokens["CT_SCENE"] = self._scene
        tokens["CT_PROJECT"] = self.project_name

        for token in tokens:
            hou.putenv(token, tokens[token])

        return tokens

    def get_args(self):
        """Prepare the args for submission to conductor.

        This is a list where there is one args object for
        each Conductor job. The project, notifications, and
        upload args are the same for all jobs, so they are
        set here. Other args are provided by Job objects and
        updated with these submission level args to form
        complete jobs.
        """
        result = []
        submission_args = {}

        submission_args["local_upload"] = self._upload["local"]
        submission_args["upload_only"] = self._upload["only"]
        submission_args["force"] = self._upload["force"]
        submission_args["project"] = self.project_name

        if self.email_addresses:
            addresses = ", ".join(self.email_addresses)
            submission_args["notify"] = {"emails": addresses, "slack": []}
        else:
            submission_args["notify"] = None

        for job in self._jobs:
            args = job.get_args()
            args.update(submission_args)
            result.append(args)
        return result

    @property
    def local_upload(self):
        """local_upload."""
        return self._upload["local"]

    @property
    def force_upload(self):
        """force_upload."""
        return self._upload["force"]

    @property
    def upload_only(self):
        """upload_only."""
        return self._upload["only"]

    @property
    def scene(self):
        """scene."""
        return self._scene

    @property
    def node_name(self):
        """node_name."""
        return self._node.name()

    @property
    def project_id(self):
        """project_id."""
        return self._project["id"]

    @property
    def project_name(self):
        """project_name."""
        return self._project["name"]

    @property
    def filename(self):
        """filename."""
        return hou.hipFile.name()

    @property
    def basename(self):
        """basename."""
        return hou.hipFile.basename()

    @property
    def unsaved(self):
        """unsaved."""
        return hou.hipFile.hasUnsavedChanges()

    @property
    def use_timestamped_scene(self):
        """use_timestamped_scene."""
        return self._use_timestamped_scene

    @property
    def tokens(self):
        """tokens."""
        return self._tokens

    @property
    def jobs(self):
        """jobs."""
        return self._jobs

    def has_notifications(self):
        """has_notifications."""
        return bool(self._notifications)

    @property
    def email_addresses(self):
        """email_addresses."""
        if not self.has_notifications():
            return []
        return self._notifications["email"]["addresses"]

    @property
    def email_hooks(self):
        """email_hooks."""
        if not self.has_notifications():
            return []
        return self._notifications["email"]["hooks"]
