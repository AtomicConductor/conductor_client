import datetime
import re
import json

import hou
from conductor.lib import api_client

 
from submission_tree import SubmissionTree
from job import Job
import takes
import render_source
import notifications


# Catch a timestamp of the form 2018_02_27_10_59_47 with optional
# underscore delimiters at the start and/or end of a string
TIMESTAMP_RE = re.compile(r"^[\d]{4}(_[\d]{2}){5}_*|_*[\d]{4}(_[\d]{2}){5}$")


class Submission(object):

    def __init__(self, node, **kw):
        self._node = node
        take = kw.get('take')
        self._takes = [take] if take else takes.active_takes(node)
        self._source_node = render_source.get_render_node(node)
        self._hip_basename = hou.hipFile.basename()
        self._hip_fullname = hou.hipFile.name()
        self._hip_unsaved = hou.hipFile.hasUnsavedChanges()
        self._project = self._node.parm('project').eval()
        self._notifications = notifications.get_notifications(self._node)
        self._merge_takes = bool(self._node.parm('merge_takes').eval())

        if not (self._takes and self._source_node):
            raise hou.InvalidInput(
                """Need at least one active take and a
                connected source_node to create a
                submission.""")
        self._tokens = self._collect_tokens()

    def _project_name(self):
        projects = json.loads(self._node.parm('projects').eval())
        return [project["name"]
                for project in projects if project['id'] == self._project][0]

    def _stripped_hip(self):
        """Strip off the extension and timestamp from start or end."""
        no_ext = re.sub('\.hip$', '', self._hip_basename)
        return re.sub(TIMESTAMP_RE, '', no_ext)

    def dry_run(self):
        """Build an object that fully describes the submission without mutating
        anything."""

        # expander = Expander(**self._tokens)

        submission = {
            "submitter": self._node.name(),
            "tokens": self._tokens,
            "filename": self._hip_fullname,
            "source": self._source_node.name(),
            "type": self._source_node.type().name(),
            "project": self._project,
            "notifications": self._notifications,
            "unsaved": self._hip_unsaved,
            "merge_takes": self._merge_takes,
            "jobs": []
        }

        for take in self._takes:
            with takes.take_context(take):
                job = Job(self._node)
                submission["jobs"].append(job.dry_run(self._tokens))

        # t = self._prepare_for_tree_view(submission)
        submission_tree = SubmissionTree()
        submission_tree.populate(submission)
        submission_tree.show()
        hou.session.dummy = submission_tree

    def _collect_tokens(self):
        """Tokens are variables to help the user build strings.

        The user interface has fields for strings such as
        job title, render command, and various paths. The
        user can enclose any of these tokens in angle
        brackets and they will be resolved for the
        submission.

        """
        tokens = {}
        tokens["timestamp"] = datetime.datetime.now().strftime(
            '%Y_%m_%d_%H_%M_%S')
        tokens["submitter"] = self._node.name()
        tokens["project"] = self._project_name()
        tokens["source"] = self._source_node.name()
        tokens["type"] = self._source_node.type().name()
        tokens["hipbase"] = self._stripped_hip()
        tokens["takes"] = (", ").join([take.name() for take in self._takes])

        return tokens
