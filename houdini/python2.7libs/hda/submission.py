import datetime
import re
from contextlib import contextmanager
import hou
import hda


@contextmanager
def take_context(take):
    """Put houdini in the context of a take to run some code."""
    remember = hou.takes.currentTake()
    hou.takes.setCurrentTake(take)
    yield
    hou.takes.setCurrentTake(remember)


# Catch a timestamp of the form 2018_02_27_10_59_47 with optional
# underscore delimiters at the start and/or end of a string
TIMESTAMP_RE = re.compile(r"^[\d]{4}(_[\d]{2}){5}_*|_*[\d]{4}(_[\d]{2}){5}$")


class Submission(object):

    def __init__(self, node, **kw):
        self._node = node
        take = kw.get('take')
        self._takes = [take] if take else hda.takes.active_takes(node)
        self._source_node = hda.render_source.get_render_node(node)
        self._hip_basename = hou.hipFile.basename()
        self._hip_fullname = hou.hipFile.name()

        if not (self._takes and self._source_node):
            raise hou.InvalidInput(
                "Need at least one active take and a connected source_node to create a submission.")
        self._tokens = self._collect_tokens()

    def _collect_tokens(self):
        """Tokens are string kv pairs used for substitutions.

        Notice how these are values that can't change per take/Job. You can't  

        """
        tokens = {}
        tokens["timestamp"] = datetime.datetime.now().strftime(
            '%Y_%m_%d_%H_%M_%S')
        tokens["submitter"] = self._node.name()
        tokens["project"] = self._node.parm('project').eval()
        tokens["source"] = self._source_node.name()
        tokens["type"] = self._source_node.type().name()
        tokens["hipbase"] = self._stripped_hip()

        return tokens

    def _stripped_hip(self):
        """Strip off the extension and timestamp from start or end."""
        no_ext = re.sub('\.hip$', '', self._hip_basename)
        return re.sub(TIMESTAMP_RE, '', no_ext)
        

    def dry_run(self):
        """Build an object that fully describes the submission without mutating
        anything."""

        expander = hda.expansion.Expander(**self._tokens)

        submission = {
            "tokens": self._tokens,
            "jobs": []
        }

        for take in self._takes:
            with take_context(take):
                job = hda.job.Job(self._node)
                submission["jobs"].append(job.dry_run(self._tokens))

        print submission





