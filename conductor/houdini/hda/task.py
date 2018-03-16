from conductor.houdini.lib.expansion import Expander


class Task(object):
    """Prepare a Task."""

    def __init__(self, clump, command, parent_tokens):
        self._clump = clump
        self._tokens = self._collect_tokens(parent_tokens)
        expander = Expander(**self._tokens)
        self._command = expander.evaluate(command)

    def _collect_tokens(self, parent_tokens):
        """Tokens are string kv pairs used for substitutions."""
        tokens = parent_tokens.copy()

        clump_type = type(self._clump).__name__.lower()[:-5]
        tokens["clumptype"] = clump_type

        tokens["clump"] = str(self._clump)
        tokens["clumplength"] = str(len(self._clump))
        tokens["clumpstart"] = str(self._clump.start)
        tokens["clumpend"] = str(self._clump.end)
        tokens["clumpstep"] = str(
            self._clump.step) if clump_type == "regular" else "~"

        return tokens

    def remote_data(self):
        return {
            "frames": str(self._clump),
            "command": self._command
        }

    @property
    def clump(self):
        return self._clump

    @property
    def command(self):
        return self._command

    @property
    def tokens(self):
        return self._tokens


    # def dry_run(self, job_tokens):
    #     """Build an object that fully describes the task without mutating
    #     anything."""
    #     # tokens = job_tokens.copy()
    #     # tokens.update(self._tokens)
    #     # expander = Expander(**tokens)

    #     # task = {}
    #     # task["tokens"] = tokens
    #     task["command"] = expander.evaluate(
    #         self._node.parm("task_command").eval())
    #     # task["clump"] = self._clump
    #     return task
