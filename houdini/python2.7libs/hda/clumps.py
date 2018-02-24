
import re
import math
from itertools import islice

NUMBER_RE = re.compile(r"^(\d+)$")
# Catch a frame range with optional step
RANGE_RE = re.compile(r"^(?:(\d+)-(\d+)(?:x(\d+))?)+$")


def to_xrange(tup):
    """Generate a valid xrange from 3 frame spec numbers.

    Numbers may be strings, start may be after end, step may
    be None. We add 1 to the end because when a user
    specifies the end val she expects it to be inclusive.

    """
    if len(tup) < 2:
        raise ValueError("Not enough values")
    start, end = sorted([int(n) for n in [tup[0], tup[1]]])
    step = int(tup[2]) if len(tup) == 3 else 1
    return xrange(start, (end + 1), step)


class Clump(object):

    """A Clump is a wrapper around an iterable of frames.

    It can generate a list of filenames with numbers
    substituted

    """

    def __init__(self):
        self._iterable = None

    def __len__(self):
        return len(self._iterable)

    def __iter__(self):
        return iter(self._iterable)

    def __str__(self):
        return str(self._iterable)

    @property
    def is_regular(self):
        return isinstance(self, RegularClump)

    @property
    def is_irregular(self):
        return isinstance(self, IrregularClump)

    @property
    def first(self):
        return self._iterable[0]

    @property
    def last(self):
        return self._iterable[-1]

    def format(self, template):
        """Insert each number in a template.

        For example if format string is
        "foo/%02d/fn.%04d.ass" Then the result array will
        contain: "foo/01/fn.0001.ass" "foo/02/fn.0002.ass"
        and so on

        """
        num_tokens = template.count('%')
        arr = []
        for i in self._iterable:
            substitutions = tuple([i] * num_tokens)
            arr.append(template % substitutions)
        return arr

    def string_list(self):
        """return all frames as string."""
        return ",".join(['%s' % x for x in self._iterable])


class RegularClump(Clump):

    """A RegularClump is an itetatable that wraps an xrange.

    It can be initialized with two or three numbers start,
    end, <step> or a "string start-endxstep" where xstep is
    optional It has inclusive upper bound.

    """

    def __init__(self, *args):
        """one_line_doc_string."""
        err = "Args must be (start, end, <step>) or ('start-end<xstep>')"
        Clump.__init__(self)
        start, end, step = [0, 0, 1]
        nargs = len(args)
        if nargs in [2, 3]:
            start = args[0]
            end = args[1]
            if nargs == 3:
                step = args[2]
        elif nargs == 1:
            range_match = RANGE_RE.match(args[0])
            if not range_match:
                raise TypeError(err)
            start, end, step = [int(n or 1) for n in range_match.groups()]
        else:
            raise TypeError(err)

        self._start, self._end = sorted([start, end])
        self._step = step
        self._iterable = xrange(start, end + 1, step)

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


# rc = RegularClump("1-10x77")
# print rc
# print rc.start
# print rc.end
# print rc.step

# print rc
# # print [i for i in rc]

# # for i in rc:
# #     print i

# for f in rc.format("foo/%02d/fn.%04d.ass"):
#     print f


class IrregularClump(Clump):

    """An irregularClump holds a sorted list of frames.

    It will print itself as "IrregularClump(<first>~<last>)..." To see the fil

     unless
    its longer than 6 elements, in which case it will
    be truncated "first ~irregular~ last"

    Full list can be created as a single comma delimited
    string with expand()

    """

    def __init__(self, iterable):
        """one_line_doc_string."""
        Clump.__init__(self)
        self._iterable = sorted(list(iterable))

    @property
    def frames(self):
        return self._iterable

    def __str__(self):
        return "%s(%s~%s)" % (self.__class__.__name__,
                              self.first, self.last)


class ClumpCollection(object):
    """one_line_doc_string."""

    @staticmethod
    def generate_linear_clumps(start, end, step, clump_size):
        # result = []
        frames = xrange(start, end + 1, step)
        num = len(frames)
        for first_index in xrange(0, num, clump_size):
            last_index = min(first_index + (clump_size - 1), num - 1)
            yield RegularClump(
                frames[first_index],
                frames[last_index],
                step)

    @staticmethod
    def generate_cycle_clumps(start, end, step, clump_size):
        """Spread frames over clumps.

        Say we have (1-200x2), thats 100 frames to render,
        but we only have 10 boxes. using cycleClumps, and
        setting clumpsize to 10, the first clump will render
        1,21,41 ... 181 which means the artist will see
        early on, a selection of frames spread throughout
        the animation.

        """
        # result = []
        num = len(xrange(start, end + 1, step))
        nclumps = int(math.ceil(num / float(clump_size)))
        gap = step * nclumps
        for i in xrange(0, nclumps):
            istart = int(start + (i * step))
            iend = int(end)
            igap = int(gap)
            repeats = ((iend - 1) - istart) / igap
            if not repeats:
                igap = 1
            iend = istart + (repeats * igap)
            yield RegularClump(istart, iend, igap)

    @staticmethod
    def to_clump(iterable):
        """Return regular or irregular clump.

        If frame_list is equal to a range made from
        first element, last element, and gap between
        first and second element,
        then the clump is regular - which means
        it is in ascending order and has the same gap
        between consecutive elements

        """
        frames = sorted(iterable)

        if len(frames) == 1:
            return RegularClump(frames[0], frames[0])

        step = frames[1] - frames[0]

        regular_range = range(frames[0], frames[-1] + 1, step)

        if regular_range == frames:
            return RegularClump(frames[0], frames[-1], step)
        return IrregularClump(frames)

    @staticmethod
    def generate_clumps_from_list(the_list, clump_size):
        ptr = iter(the_list)
        clump = list(islice(ptr, clump_size))
        while clump:
            yield ClumpCollection.to_clump(clump)
        clump = list(islice(ptr, clump_size))

    @classmethod
    def from_spec(cls, frame_spec, clump_size=1):
        err = "Args must be a frame spec and a an optional clump size"
        result = set()
        val = frame_spec.strip(',')
        for part in [x.strip() for x in val.split(',')]:
            number_matches = NUMBER_RE.match(part)
            range_matches = RANGE_RE.match(part)
            if number_matches:
                vals = number_matches.groups()
                result = result.union([int(vals[0])])
            elif range_matches:
                tup = to_xrange(range_matches.groups())
                result = result.union(tup)

        result = sorted(result)

        clumps = ClumpCollection.generate_clumps_from_list(result, clump_size)
        return cls(clumps, clump_size)

    @classmethod
    def from_range(cls, start, end, **kw):
        start, end, step = to_xrange((start, end, kw.get('step', 1)))
        clump_size = max(1, kw.get('clump_size', 1))
        cycle = kw.get('cycle', False)
        clumps = []
        if cycle:
            clumps = ClumpCollection.generate_cycle_clumps(
                start, end, step, clump_size)
        else:
            clumps = ClumpCollection.generate_linear_clumps(
                start, end, step, clump_size)
        return cls(clumps, clump_size)

    def __init__(self, clumps, clump_size):
        self._clump_size = clump_size
        self._clumps = clumps

    @property
    def clumps(self):
        """one_line_doc_string."""
        return self._clumps

    def __iter__(self):
        return iter(self._clumps)

    def __len__(self):
        return len(self._clumps)

    def __str__(self):
        return '[' + (', ').join(str(clump) for clump in self._clumps) + ']'

    @property
    def total_length(self):
        """Sum of frames in all clumps."""
        count = 0
        for clump in self._clumps:
            count += len(clump)
        return count
