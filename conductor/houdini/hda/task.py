import hou
# from conductor.houdini.lib.expansion import Expander


class Task(object):
    """Prepare a Task."""

    def __init__(self, clump, command, parent_tokens):
        self._clump = clump
        self._tokens = self._collect_tokens(parent_tokens)
 
        self._command = hou.expandString(command)

    def _collect_tokens(self, parent_tokens):
        """Tokens are string kv pairs used for substitutions."""

        tokens = {}
        clump_type = type(self._clump).__name__.lower()[:-5]
        tokens["CT_CLUMPTYPE"] = clump_type
        tokens["CT_CLUMP"] = str(self._clump)
        tokens["CT_CLUMPLENGTH"] = str(len(self._clump))
        tokens["CT_CLUMPSTART"] = str(self._clump.start)
        tokens["CT_CLUMPEND"] = str(self._clump.end)
        tokens["CT_CLUMPSTEP"] = str(
            self._clump.step) if clump_type == "regular" else "~"

        for token in tokens:
            hou.putenv(token, tokens[token])
        tokens.update(parent_tokens)

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
 