import datetime
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


class Submission(object):

    def __init__(self, node, **kw):
        self._node = node
        take = kw.get('take')
        self._takes = [take] if take else hda.takes.active_takes(node)
        self._source_node = hda.render_source.get_render_node(node)
        if not (self._takes and self._source_node):
            raise hou.InvalidInput("Need at least one active take and a connected source_node to create a submission.")
        self._tokens = self._collect_tokens()

    def _collect_tokens(self):
        """Tokens are string kv pairs used for substitutions. Any we generate here will be available to sr"""
        tokens = {}
        tokens["timestamp"] = datetime.datetime.now().strftime(
            '%Y_%m_%d_%H_%M_%S')
        tokens["submitter"] = self._node.name()
        tokens["project"] = self._node.parm('project').eval()
        tokens["source"] = self._source_node.name()
        tokens["type"] = self._source_node.type().name()
        return tokens

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


 

