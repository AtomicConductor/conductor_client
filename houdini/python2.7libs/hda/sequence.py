"""A Sequence holds frame numbers which can be clumped together.

It can be initialized with a range or with a list of
numbers. It has two properties that define how clumps will
be made: clump_size and cycle.

"""
import re
import math

# Catch a number
NUMBER_RE = re.compile(r"^(\d+)$")

# Catch a frame range with optional step
RANGE_RE = re.compile(r"^(?:(\d+)-(\d+)(?:x(\d+))?)+$")


def resolve_start_end_step(*args):
    """Generate a valid start, end, step.

    Args may be individual ints or strings. Start may be
    after end. Step may be None or missing. Arg may be a
    single range string as 'start-endxstep' where step is
    optional.

    """
    if len(args) == 1:
        range_match = RANGE_RE.match(args[0])
        if not range_match:
            raise ValueError("Single arg must be 'start-end<xstep>")
        start, end, step = [int(n or 1) for n in range_match.groups()]
    else:
        start, end = [int(n) for n in [args[0], args[1]]]
        step = int(args[2]) if len(args) == 3 else 1
    start, end = sorted([start, end])
    if step < 1 or start < 0:
        raise ValueError(
            "Args must have non-negative range and a positive step")
    return (start, end, step)


class Clump(object):
    """A Clump is a sorted iterable representing a sequence of frames."""
    @staticmethod
    def create(iterable):
        """Factory makes one of the Clump subclasses.

        If iterable is equal to a range made from first
        element, last element, and gap between first and
        second element, then the clump is regular, which
        means it is in ascending order and has the same gap
        between consecutive elements. Otherwise it is
        irregular.

        """
        frames = sorted(set(iterable))
        if len(frames) == 1:
            return RegularClump(frames[0], frames[0])
        step = frames[1] - frames[0]
        regular_range = range(frames[0], frames[-1] + 1, step)
        if regular_range == frames:
            return RegularClump(frames[0], frames[-1], step)
        return IrregularClump(frames)

    def format(self, template):
        """Insert each number in a template.

        For example if format string is
        "foo/%02d/fn.%04d.ass" Then the result array will
        contain: "foo/01/fn.0001.ass" "foo/02/fn.0002.ass"
        and so on

        """
        num_tokens = template.count('%')
        return [template % ((i,) * num_tokens) for i in self._iterable]

    def __init__(self):
        self._iterable = None

    def __len__(self):
        return len(self._iterable)

    def __iter__(self):
        return iter(self._iterable)

    def __str__(self):
        return str(self._iterable)


class RegularClump(Clump):
    """A RegularClump is an itetatable that wraps an xrange.

    It can be initialized with two or three numbers start,
    end, <step> or a "string start-endxstep" where step is
    optional It has inclusive upper bound.

    """

    def __init__(self, *args):
        """one_line_doc_string."""
        Clump.__init__(self)
        self._start, self._end, self._step = resolve_start_end_step(*args)
        self._iterable = xrange(self._start, self._end + 1, self._step)

    @property
    def step(self):
        return self._step

    @property
    def start(self):
        return self._start

    @property
    def end(self):
        return self._end

    def __str__(self):
        return "%s(%s-%sx%s)" % (self.__class__.__name__,
                                 self.start, self.end, self.step)


class IrregularClump(Clump):
    """A sorted list of frames that cannot be represented by a range."""

    def __init__(self, iterable):
        Clump.__init__(self)
        self._iterable = sorted(list(iterable))

    def __str__(self):
        return "%s(%s~%s)" % (self.__class__.__name__,
                              self._iterable[0], self._iterable[-1])


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
    def from_spec(cls, frame_spec, **kw):
        """Factory method to create Sequence from spec string.

        Spec must be reducible to a list of frames. Valid
        spec consists of either numbers or ranges separated
        by commas. Ranges can have an optional step value.
        Example valid custom range spec: "120, 5,
        26-76,19-23x4, 1000-2000, 3,9,"

        """

        the_set = set()
        for part in [x.strip() for x in frame_spec.split(',')]:
            number_matches = NUMBER_RE.match(part)
            if number_matches:
                vals = number_matches.groups()
                the_set = the_set.union([int(vals[0])])
            elif RANGE_RE.match(part):
                start, end, step = resolve_start_end_step(part)
                the_set = the_set.union(xrange(start, end + 1, step))
            else:
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
        self._frames = frames
        self._clump_size = kw.get('clump_size', 1)
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
        return [Clump.create(self._frames[i:i + self._clump_size])
                for i in xrange(0, len(self._frames), self._clump_size)]

    def clumps(self):
        """return list of clumps according to size and cycle."""
        if self._cycle:
            return self._cycle_clumps()
        return self._linear_clumps()

    def clump_count(self):
        """Calculate the number of clumps that will be emitted."""
        return int(math.ceil(len(self._frames) / float(self._clump_size)))

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
        """Frames in the order computed from clump_size and cycle."""
        return iter([item for sublist in self.clumps() for item in sublist])

    def __len__(self):
        return len(self._frames)

    def __str__(self):
        """String representation containes the stringified clumps."""
        seq = (', ').join([str(clump) for clump in self.clumps()])
        return "%s(%s)" % (self.__class__.__name__, seq)
