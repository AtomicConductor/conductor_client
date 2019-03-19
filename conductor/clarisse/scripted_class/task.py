import ix
from conductor.clarisse.scripted_class import variables

class Task(object):
    """A Task is a command and the list of frames it relates to.

    It provides a handful of tokens that can be used to
    construct the command.
    """

    def __init__(self, chunk, command_attr, parent_tokens):
        """Resolve the tokens and the command.

        After calling setenv, tokens such as start end step
        and so on are valid. So when we expand the command
        any tokens that were used are correctly resolved.

        The chunk arg is an instance of Sequence.
        """
        self._chunk = chunk
        self._tokens = self._setenv(parent_tokens)
  
        command_attr.activate_expression(False)
        command_attr.activate_expression(True)


        # results = ix.api.CoreStringArray()
        # command_attr.get_values(results)
        # self._command = results[0] 
        
        self._command = command_attr.get_string()

    def _setenv(self, parent_tokens):
        """Env tokens at the task level.

        Task level tokens are joined with Job and submission
        level tokens so that all tokens are available when
        constructing the task command.

        Example:
        python myCmd.py -s $CT_CHUNKSTART -e $CT_CHUNKEND -n $CT_SOURCE -f $CT_RENDER_PACKAGE
        """

        tokens = {}
        chunk_type = "regular" if self._chunk.is_progression() else "irregular"
        tokens["CT_CHUNKTYPE"] = chunk_type
        tokens["CT_CHUNK"] = str(self._chunk).replace("-",":").replace("x","%").replace(",",";")
        tokens["CT_CHUNKLENGTH"] = str(len(self._chunk))
        tokens["CT_CHUNKSTART"] = str(self._chunk.start)
        tokens["CT_CHUNKEND"] = str(self._chunk.end)
        tokens["CT_CHUNKSTEP"] = str(
            self._chunk.step) if chunk_type == "regular" else "~"


        for token in tokens:
            variables.put(token, tokens[token])
        tokens.update(parent_tokens)
        return tokens



    def data(self):
        """The command and frame spec."""
        return {
            "frames": str(self._chunk),
            "command": self._command
        }

    @property
    def chunk(self):
        return self._chunk

    @property
    def command(self):
        return self._command

    @property
    def tokens(self):
        return self._tokens
