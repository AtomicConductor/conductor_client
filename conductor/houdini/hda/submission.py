import datetime
import json
import hou

from conductor.houdini.lib import data_block
from conductor.houdini.hda import submission_ui, types, notifications_ui
from conductor.houdini.hda.job import Job


class Submission(object):

    def __init__(self, node, **kw):
        self._node = node
        vendor, nodetype, version = node.type().name().split("::")
        if types.is_job_node(self._node):
            self._nodes = [node]
        else:
            self._nodes = node.inputs()

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
        

        self._tokens = self._collect_tokens()
  

        self._user = hou.getenv('USER')
        self._jobs = []

        for node in self._nodes:
            job = Job(node, self._tokens, self._scene)
            self._jobs.append(job)

    def _get_project_name(self):
        projects = data_block.ConductorDataBlock(product="houdini").projects()

        project_names = [project["name"]
                         for project in projects if project['id'] == self._project_id]
        if not project_names:
            raise hou.InvalidInput(
                "%s %s is an invalid project." %
                self._node.name(), self._project_id)
        return project_names[0]

    def _collect_tokens(self):
        """Tokens are variables to help the user build strings.

        The user interface has fields for strings such as
        job title, render command, and various paths. The
        user can enclose any of these tokens in angle
        brackets and they will be resolved for the
        submission.

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


    def remote_args(self):

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
            args = job.remote_args()
            args.update(submission_args)
            result.append(args)
        return result

    @property
    def user(self):
        return self._user

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
