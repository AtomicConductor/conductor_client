import re

import progressions as prog

# Catch a number
NUMBER_RE = re.compile(r"^(\d+)$")

# Catch a frame range with optional step
RANGE_RE = re.compile(r"^(?:(\d+)-(\d+)(?:x(\d+))?)+$")


def resolve_start_end_step(*args):
    """Generate a valid start, end, step.

    Args may be individual ints or strings. Start may be
    after end. Step may be None or missing. Arg may be a
    single range string as 'start-endxstep' where end and
    step are optional.

    """
    if len(args) == 1:
        number_match = NUMBER_RE.match(args[0])
        range_match = RANGE_RE.match(args[0])
        if not (range_match or number_match):
            raise ValueError("Single arg must be 'start<-end<xstep>>")
        if range_match:
            start, end, step = [int(n or 1) for n in range_match.groups()]
        else:
            start, end, step = [int(number_match.groups()[0]), int(
                number_match.groups()[0]), 1]
    else:
        start, end = [int(n) for n in [args[0], args[1]]]
        step = int(args[2]) if len(args) == 3 else 1
    start, end = sorted([start, end])
    if step < 1 or start < 0:
        raise ValueError(
            "Args must have non-negative range and positive step")
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

    @staticmethod
    def regular_clumps(iterable):
        """Factory makes list of regular clumps from input.

        The input may be irregular, so we split it into
        arithmetic progressions and then make clumps from
        the results.

        """
        progressions = prog.create(iterable)
        return [Clump.create(p) for p in progressions]

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
        raise NotImplementedError()


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
        if self.start == self.end:
            return str(self.start)
        if self.step == 1:
            return "%s-%s" % (self.start, self.end)
        return "%s-%sx%s" % (self.start, self.end, self.step)

    def __repr__(self):
        return "%s(\"%r-%rx%r\")" % (self.__class__.__name__,
                                     self.start, self.end, self.step)


class IrregularClump(Clump):
    """A sorted list of frames that cannot be represented by a range."""

    def __init__(self, iterable):
        Clump.__init__(self)
        self._iterable = sorted(list(iterable))

    @property
    def start(self):
        return self._iterable[0]

    @property
    def end(self):
        return self._iterable[-1]

    def __str__(self):
        progressions = prog.create(self._iterable)
        clumps = [Clump.create(p) for p in progressions]
        return (",").join([str(clump) for clump in clumps])
        # return "%s~%s" % (self._iterable[0], self._iterable[-1])

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._iterable)

    def as_regular_clumps(self):
        pass
