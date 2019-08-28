"""
Build an object to represent a task to be run on a render node.
"""

from conductor import CONFIG
from conductor.native.lib.expander import Expander


class Task(object):
    """A Task has a command and the list of frames.

    It provides a handful of tokens that can be used to construct the
    command.
    """

    def __init__(self, chunk, command_attr, sources, tile_spec, parent_tokens):
        """
        Build the Task object.

        Resolve the tokens and the command. After calling set_tokens, tokens
        such as start end step and so on are valid. So when we expand the
        command any tokens that were used are correctly resolved.

        Args: 
            chunk (Sequence): The frames to be rendered. command_attr
            (OfAttr): The task template attribute. sources (list(dict(OfObject,
            Sequence))):  list of images along with a sequence that represents
            the frames they will be rendered for. tile_spec (tuple): The number
            of tiles and the current tile number. parent_tokens (dict):Angle
            bracket tokens.
        """

        self.chunk = chunk
        self.tile_spec = tile_spec
        self.sources = sources
        self.tokens = self._set_tokens(parent_tokens)
        expander = Expander(**self.tokens)
        self.command = expander.evaluate(command_attr.get_string())

    def _set_tokens(self, parent_tokens):
        """Env tokens at the task level.

        Task level tokens are joined with Job and submission level
        tokens so that all tokens are available when constructing the
        task command.

        As ConductorJob may contain many images, and those
        images may specify different frame ranges. The Clarisse render
        command `cnode` handles this by specifying as many frame-specs
        as there are images. For example `cnode -images img1 img2
        -frames 1-20 30-40`. For Conductor to handle this and calculate
        a command per chunk, it must intersect the chunk with the frame
        range from each image, and apply this in the <ct_chunks> token,
        which will be used by the task_template.
        """

        tokens = {}

        chunks = []
        image_names = []
        for source in self.sources:
            intersection = self.chunk.intersection(source["sequence"])
            if intersection:
                chunks.append(intersection.to(":", "%", "; "))
                image_names.append(source["image"].get_full_name())

        tokens["ct_tile_number"] = str(self.tile_spec[1])
        tokens["ct_chunks"] = " ".join(chunks)
        tokens["ct_sources"] = " ".join(image_names)
        tokens["ct_chunklength"] = str(len(self.chunk))
        tokens["ct_chunkstart"] = str(self.chunk.start)
        tokens["ct_chunkend"] = str(self.chunk.end)

        tokens.update(parent_tokens)
        return tokens

    def data(self):
        """
        The command and frame spec.

        Returns:
            dict: Frames withh which to determine if its a scout frame, and the
            resolved command itself.
        """
        return {"frames": str(self.chunk), "command": self.command}
