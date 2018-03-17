"""Manage sequences of frames with optional clumping.

It can emit clumps according to a specified policy, for
example, linearly or cycle. Where cycle will distrtibute
frames across clumps such that the first frame completed by
each clump will together form a continuous sequence. For
rationale see _cycle_clumps. It can be initialized with a
range or with a list of numbers. It has two properties that
define how clumps will be made: clump_size and cycle.

"""

import math

from conductor.houdini.lib.clump import (
    NUMBER_RE,
    RANGE_RE,
    resolve_start_end_step,
    Clump,
    RegularClump,
    IrregularClump)

import conductor.houdini.lib.progressions as prog


class Sequence(object):
    """Collection of frames with the ability to generate clumps."""

    @staticmethod
    def is_valid_spec(spec):
        try:
            value = spec.strip(',')
        except AttributeError:
            raise TypeError("Frame spec must be a string")
        valid = bool(value)
        for part in [x.strip() for x in value.split(',')]:
            if not (NUMBER_RE.match(part) or RANGE_RE.match(part)):
                valid = False
                break
        return valid

    @classmethod
    def from_spec(cls, frame_spec_ui, **kw):
        """Factory method to create Sequence from spec string.

        Spec must be reducible to a list of frames. Valid
        spec consists of either numbers or ranges separated
        by commas. Ranges can have an optional step value.
        Example valid custom range spec: "120, 5,
        26-76,19-23x4, 1000-2000, 3,9,".

        """

        the_set = set()
        for part in [x.strip() for x in frame_spec_ui.split(',')]:
            number_matches = NUMBER_RE.match(part)
            if number_matches:
                vals = number_matches.groups()
                the_set = the_set.union([int(vals[0])])
            elif RANGE_RE.match(part):
                start, end, step = resolve_start_end_step(part)
                the_set = the_set.union(xrange(start, end + 1, step))
            elif part:
                # There should be no other non-empty parts
                raise ValueError("Invalid frame spec")
        frames = sorted(the_set)
        return cls(frames, **kw)

    @classmethod
    def from_range(cls, start, end, **kw):
        """Factory method to create Sequence from range.

        Range must have start and end. Step, clump-size and
        cycle method may be specified in keyword args

        """
        start, end, step = resolve_start_end_step(
            start, end, kw.get('step', 1))
        frames = range(start, end + 1, step)
        return cls(frames, **kw)

    def __init__(self, frames, **kw):
        """Instantiate from iterable.

        If frames is given as a set, convert to a list

        """
        self._frames = frames
        if not hasattr(frames, '__getitem__'):
            self._frames = list(frames)
        self._clump_size = max(1, kw.get('clump_size', 1))
        self._cycle = kw.get('cycle', False)

    def _cycle_clumps(self):
        """Generate clumps with frame cycling.

        Say we have 100 frames to render (1-100). With
        clumpsize of 5, there will be 20 instances. The
        first clump will render 1, 21, 41, 61 81, the second
        clump 2, 22, 42, 62, 82 and so on, which means the
        artist will see frames 1,2,3,4...20 early on. This
        may be useful to check for frame coherence artifacts
        without waiting for a whole clump to render on one
        machine.

        """
        num_clumps = self.clump_count()
        result = [[] for i in range(num_clumps)]
        for index, frame in enumerate(self._frames):
            idx = index % num_clumps
            result[idx].append(frame)
        return [Clump.create(x) for x in result]

    def _linear_clumps(self):
        """Generate clumps in sorted order."""
        result = []
        for i in xrange(0, len(self._frames), self._clump_size):
            result.append(Clump.create(self._frames[i:i + self._clump_size]))
        return result

    def clumps(self):
        """return list of clumps according to size and cycle."""
        if self._cycle:
            return self._cycle_clumps()
        return self._linear_clumps()

    def clump_count(self):
        """Calculate the number of clumps that will be emitted."""
        return int(math.ceil(len(self._frames) / float(self._clump_size)))

    def intersection(self, iterable):
        common_frames = set(self._frames).intersection(set(iterable))
        return Sequence(common_frames)

    def best_clump_size(self):
        """Return clumpsize for best distribution.

        The result is the smallest clumpsize that maintains
        the current clump_count.

        """
        if not self._frames:
            return
        return math.ceil(len(self._frames) / float(self.clump_count()))

    @property
    def clump_size(self):
        return self._clump_size

    @clump_size.setter
    def clump_size(self, value):
        if value < 1:
            raise ValueError("Clump size can't be zero")
        self._clump_size = value

    @property
    def cycle(self):
        return self._cycle

    @cycle.setter
    def cycle(self, value):
        self._cycle = bool(value)

    def __iter__(self):
        """Frames in the order computed using clump_size and cycle.

        WHY?

        """
        return iter([item for sublist in self.clumps() for item in sublist])

    def __len__(self):
        return len(self._frames)

    def __str__(self):
        """String representation containes the stringified clumps."""
        seq = (', ').join([repr(clump) for clump in self.clumps()])
        return "[%s]" % seq

    def __repr__(self):
        """Repr containes whats necessary to init."""
        return "%s(%r, clump_size=%r, cycle=%r)" % (
            self.__class__.__name__, self._frames, self._clump_size, self._cycle)
