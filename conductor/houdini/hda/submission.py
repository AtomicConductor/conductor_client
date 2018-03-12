import datetime
import re
import json

import hou
from conductor.lib import api_client


from submission_tree import SubmissionTree
from job import Job
 


# Catch a timestamp of the form 2018_02_27_10_59_47 with optional
# underscore delimiters at the start and/or end of a string
TIMESTAMP_RE = re.compile(r"^[\d]{4}(_[\d]{2}){5}_*|_*[\d]{4}(_[\d]{2}){5}$")


class Submission(object):

    def __init__(self, node, **kw):
        self._node = node
        vendor, nodetype, version = node.type().name().split("::")
        if nodetype == "submitter":
            self._nodes = [node]
        else: 
            # get list of inputs later
            pass

        self._hip_basename = hou.hipFile.basename()
        self._hip_fullname = hou.hipFile.name()
        self._hip_unsaved = hou.hipFile.hasUnsavedChanges()
        self._tokens = self._collect_tokens()

   
    def _stripped_hip(self):
        """Strip off the extension and timestamp from start or end."""
        no_ext = re.sub('\.hip$', '', self._hip_basename)
        return re.sub(TIMESTAMP_RE, '', no_ext)

    def dry_run(self):
        """Build an object that fully describes the submission without mutating
        anything."""

        # expander = Expander(**self._tokens)
        job = Job(self._node)
        submission = {
            "submission": self._node.name(),
            "tokens": self._tokens,
            "filename": self._hip_fullname,
            "unsaved": self._hip_unsaved,
            "jobs": []
        }

        for node in self._nodes:
            job = Job(node)
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
        tokens["submission"] = self._node.name()

        tokens["hipbase"] = self._stripped_hip()


        return tokens
