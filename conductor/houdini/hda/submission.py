"""Build an object to represent a Conductor submission."""

import datetime
import json
import hou

from conductor.houdini.lib import data_block
from conductor.houdini.hda import submission_ui, types, notifications_ui, driver_ui
from conductor.houdini.hda.job import Job


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
        vendor, nodetype, version = node.type().name().split("::")
        if types.is_job_node(self._node):
            self._jobs = [node]
        else:
            self._jobs = node.inputs()

        self._timestamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        self._hipbase = submission_ui.stripped_hip()
        self._use_timestamped_scene = bool(
            self._node.parm("use_timestamped_scene").eval())
        self._scene = submission_ui.set_scene_name(self._node, self._timestamp)
        self._local_upload = bool(self._node.parm("local_upload").eval())
        self._force_upload = bool(self._node.parm("force_upload").eval())
        self._upload_only = bool(self._node.parm("upload_only").eval())
        self._notifications = notifications_ui.get_notifications(self._node)
        self._project_id = self._node.parm('project').eval()
        self._project_name = self._get_project_name()

        self._tokens = self._setenv()

        self._jobs = []
        for node in self._jobs:
            job = Job.create(node, self._tokens, self._scene)
            self._jobs.append(job)

    def _get_project_name(self):
        """Get the project name by looking up its ID.

        Just in case the current project is no longer in the
        list of shared projects, we throw an error if its
        not found.
        """
        projects = data_block.ConductorDataBlock(product="houdini").projects()

        project_names = [project["name"]
                         for project in projects if project['id'] == self._project_id]
        if not project_names:
            raise hou.InvalidInput(
                "%s %s is an invalid project." %
                self._node.name(), self._project_id)
        return project_names[0]

    def _setenv(self):
        """Env tokens are variables to help the user build strings.

        The user interface has fields for strings such as
        job title, task command, metadata. The user can use
        these tokens, prefixed with a $ symbol, to build
        those strings. Tokens at the Submission level are
        also available in Job level fields, and likewise
        tokens at the Job level are available in Task level
        fields. However, it makes no sense the other way,
        for example you can't use a clump token (available
        at Task level) in a Job title because a clump
        changes for every task.

        We use hou.putenv() which basically sets these as
        global env vars in the scene. Once this is done,
        strings using these tokens are expanded correctly. In
        fact we don't need these tokens to be stored on the
        Submission object (or Job or Task) for the submission
        to succeed. The only reason we store them is to
        display them in a dry-run scenario.
        """
        tokens = {}
        tokens["CT_TIMESTAMP"] = self._timestamp
        tokens["CT_SUBMITTER"] = self._node.name()
        tokens["CT_HIPBASE"] = self._hipbase
        tokens["CT_SCENE"] = self._scene
        tokens["CT_PROJECT"] = self._project_name

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
        submission_args["local_upload"] = self._local_upload
        submission_args["upload_only"] = self._upload_only
        submission_args["force"] = self._force_upload
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
    def user(self):
        return hou.getenv('USER')

    @property
    def local_upload(self):
        return self._local_upload

    @property
    def force_upload(self):
        return self._force_upload

    @property
    def upload_only(self):
        return self._upload_only

    @property
    def scene(self):
        return self._scene

    @property
    def node_name(self):
        return self._node.name()

    @property
    def project_id(self):
        return self._project_id

    @property
    def project_name(self):
        return self._project_name

    @property
    def filename(self):
        return hou.hipFile.name()

    @property
    def basename(self):
        return hou.hipFile.basename()

    @property
    def unsaved(self):
        return hou.hipFile.hasUnsavedChanges()

    @property
    def use_timestamped_scene(self):
        return self._use_timestamped_scene

    @property
    def tokens(self):
        return self._tokens

    @property
    def jobs(self):
        return self._jobs

    def has_notifications(self):
        return bool(self._notifications)

    @property
    def email_addresses(self):
        if not self.has_notifications():
            return []
        return self._notifications["email"]["addresses"]

    @property
    def email_hooks(self):
        if not self.has_notifications():
            return []
        return self._notifications["email"]["hooks"]
