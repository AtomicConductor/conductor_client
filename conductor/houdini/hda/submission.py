import datetime
 
import json

import hou
from conductor.lib import api_client


from conductor.houdini.hda import advanced

# from submission_tree import SubmissionTree
from job import Job


# # Catch a timestamp of the form 2018_02_27_10_59_47 with optional
# # underscore delimiters at the start and/or end of a string
# TIMESTAMP_RE = re.compile(r"^[\d]{4}(_[\d]{2}){5}_*|_*[\d]{4}(_[\d]{2}){5}$")


class Submission(object):

    def __init__(self, node, **kw):
        self._node = node
        vendor, nodetype, version = node.type().name().split("::")
        if nodetype == "submitter":
            self._nodes = [node]
        else:
            # get list of inputs for submission node later
            pass

 
        self._timestamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        self._hipbase = advanced.stripped_hip()
        self._use_timestamped_scene = bool(self._node.parm("use_timestamped_scene").eval())
        self._scene = advanced.scene_name_to_use(self._node, self._timestamp)
        self._local_upload = bool(self._node.parm("local_upload").eval())
        self._force_upload = bool(self._node.parm("force_upload").eval())
        self._upload_only = bool(self._node.parm("upload_only").eval())

        self._tokens = self._collect_tokens()
        self._user = hou.getenv('USER')
        self._jobs = []

        for node in self._nodes:
            self._jobs.append(Job(node, self._tokens))

    def _collect_tokens(self):
        """Tokens are variables to help the user build strings.

        The user interface has fields for strings such as
        job title, render command, and various paths. The
        user can enclose any of these tokens in angle
        brackets and they will be resolved for the
        submission.

        """
        tokens = {}
        tokens["timestamp"] = self._timestamp
        tokens["submission"] = self._node.name()
        tokens["hipbase"] = self._hipbase 
        tokens["scene"] = self._scene 
 
        return tokens

    def remote_args(self):
        result = {}
        result["local_upload"] = self._local_upload
        result["upload_only"] = self._upload_only
        result["force"] = self._force_upload
        # result["upload_paths"] = 
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
