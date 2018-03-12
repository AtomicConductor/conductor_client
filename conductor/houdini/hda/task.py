from conductor.houdini.lib.expansion import Expander


class Task(object):
    """Prepare a Task."""

    def __init__(self, node, clump):
        self._node = node
        self._clump = clump
        self._tokens = self._collect_tokens()

    def dry_run(self, job_tokens):
        """Build an object that fully describes the task without mutating
        anything."""
        tokens = job_tokens.copy()
        tokens.update(self._tokens)
        expander = Expander(**tokens)

        task = {}
        task["tokens"] = tokens
        task["command"] = expander.evaluate(
            self._node.parm("task_command").eval())
        task["clump"] = self._clump
        return task

    def _collect_tokens(self):
        """Tokens are string kv pairs used for substitutions."""

        clump_type = type(self._clump).__name__.lower()[:-5]

        tokens = {}
        tokens["clump"] = str(self._clump)
        tokens["clumplength"] = str(len(self._clump))
        tokens["clumpstart"] = str(self._clump.start)
        tokens["clumpend"] = str(self._clump.end)

        # TODO: In fact if a clump is irregular, there is no way for Houdini
        # cmdline render to render it without breaking it up some more. This
        # is what we shall do
        tokens["clumpstep"] = str(
            self._clump.step) if clump_type == "RegularClump" else "~"
        tokens["clumptype"] = clump_type
        return tokens
