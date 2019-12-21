"""A Sequence is a set of integers representing frames.

To create a sequence, use the create method and pass either:

frame spec: e.g. string  "1-10, 14, 20-50x4"
range: one, two, or three integers representing start, end, step.
iterable of ints: something that implements __iter__, e.g. a list.

Ranges in a spec are inclusive, e.g. len(Sequence("1-3")) == 3

If the input is valid, either a Sequence or a Progression will
be created. A Progression is a Sequence that can be expressed
as an arithmetic progression, i.e. first,last,step.

A Sequence has methods to split itself into chunks. Chunks are
subsequences and are themselves of type, Sequence or
Progression.

"""
import math
import re
import itertools

RX_FRAME = re.compile(r"\$(\d?)F")

PROGRESSION_SPEC_REGEX = re.compile(
    r"^(?P<first>-?\d+)(-(?P<last>-?\d+)(x(?P<step>[1-9][0-9]*))?)?$"
)

SPLIT_SPEC_REGEX = re.compile(r"[ ,,]+")


def _clamp(minval, val, maxval):
    """Clamp value to min and max."""
    return sorted([minval, val, maxval])[1]


def _resolve_frames(*args):
    if not args:
        raise TypeError("Need at least one arg")
    frames = []
    if len(args) == 1:
        arg = args[0]
        if hasattr(arg, "__iter__"):
            # arg is something like an array or range
            frames = arg
        else:
            # arg is string spec
            arg = str(arg)
            for progression in SPLIT_SPEC_REGEX.split(arg):
                match = PROGRESSION_SPEC_REGEX.match(progression)
                if not match:
                    raise ValueError("Arg must be 'start<-end<xstep>>")
                first, last, step = [
                    int(match.group("first")),
                    int(match.group("last") or match.group("first")),
                    int(match.group("step") or 1),
                ]
                if step < 1:
                    raise ValueError("Spec must have positive step values")
                first, last = sorted([first, last])
                frames += range(first, last + 1, step)
    else:  # args are inclusive range
        first, last = sorted([int(n) for n in [args[0], args[1]]])
        step = int(args[2]) if len(args) == 3 else 1
        if step < 1:
            raise ValueError("Step arg must be positive")
        frames = xrange(first, last + 1, step)
    return sorted(set(frames))


def _start_end_step(arr):
    """
    Return start, end, step if the array is a progression.
    """
    if len(arr) == 1:
        return (arr[0], arr[0], 1)
    elif len(arr) == 2:
        return (arr[0], arr[1], arr[1] - arr[0])
    elif range(arr[0], arr[-1] + 1, arr[2] - arr[1]) == arr:
        return (arr[0], arr[-1], arr[1] - arr[0])


class Sequence(object):
    """A collection of frames with the ability to generate chunks."""

    @staticmethod
    def permutations(template, **kw):
        for vals in itertools.product(
            *(iter(Sequence.create(spec)) for spec in kw.values())
        ):
            subs = dict(zip(kw, vals))
            yield template % subs

    @staticmethod
    def create(*args, **kw):
        """Factory which will create either a Sequence or a Progression.

        A Sequence is an arbitrary list of frames with unique sorted
        elements. A Progression, which is a subclass of Sequence, can be
        expressed as an arithmetic progression: i.e. start, end, step.
        """

        frames = _resolve_frames(*args)
        if not frames:
            raise TypeError("Can't create Sequence with no frames")

        progression_spec = _start_end_step(frames)
        if progression_spec:
            return Progression(*progression_spec, **kw)
        return Sequence(frames, **kw)

    def __init__(self, iterable, **kw):
        """Instantiate from list of ints.

        This method will usually be called by a factory. chunk size
        defaults to the length of the sequence if missing or if -1 is
        given. It is also clamped.
        """
        self._iterable = iterable

        num = len(self._iterable)
        chunk_size = kw.get("chunk_size", num)
        self._chunk_size = num if chunk_size < 1 else sorted([num, chunk_size])[0]

        self._chunk_strategy = kw.get("chunk_strategy", "linear")

    @property
    def start(self):
        """return the first frame."""
        return self._iterable[0]

    @property
    def end(self):
        """return the last frame."""
        return self._iterable[-1]

    def _cycle_chunks(self):
        """Generate chunks with frame cycling.

        Say we have 100 frames to render (1-100). With chunksize of 5,
        there will be 20 instances. The first chunk will render 1, 21,
        41, 61 81, the second chunk 2, 22, 42, 62, 82 and so on, which
        means the artist will see frames 1,2,3,4...20 early on. This may
        be useful to check for frame coherence artifacts without waiting
        for a whole chunk to render on one machine.
        """
        num_chunks = self.chunk_count()
        result = [[] for i in range(num_chunks)]
        for index, frame in enumerate(self._iterable):
            idx = index % num_chunks
            result[idx].append(frame)
        return [Sequence.create(x) for x in result]

    def _linear_chunks(self):
        """Generate chunks in sorted order."""
        result = []
        for i in xrange(0, len(self._iterable), self._chunk_size):
            result.append(
                Sequence.create(list(self._iterable)[i : i + self._chunk_size])
            )
        return result

    def chunks(self):
        """return list of chunks according to size and chunk strategy.

        Strategy can be linear, cycle, or progressions. Others
        may be added in future, such as binary.

        "linear" will generate Sequences by simply walking
        along the list of frames and grouping so that each
        group has chunk_size frames. i.e. Fill chunk 1 then chunk 2 ...

        "cycle" will generate Sequences by distributing the
        frames in each chunk in such a way that they get
        filled in parallel group 1 gets frame 1, group 2 gets
        frame 2 and we cycle around. See _cycle_chunks()

        "progressions" tries to walk along as in linear strategy, but
        with the constraint that each Sequence is a Progression and
        can be expressed with start, end, step. See
        Progression.factory()
        """
        if self._chunk_strategy == "cycle":
            return self._cycle_chunks()
        if self._chunk_strategy == "progressions":
            return Progression.factory(self._iterable, max_size=self._chunk_size)
        return self._linear_chunks()

    def chunk_count(self):
        """Calculate the number of chunks that will be emitted.

        If strategy is progressions we just generate them and count the
        objects. Otherwise we can calculate from the frame length and
        chunk size directly
        """
        if self._chunk_strategy == "progressions":
            return len(Progression.factory(self._iterable, max_size=self._chunk_size))
        return int(math.ceil(len(self._iterable) / float(self._chunk_size)))

    def intersection(self, iterable):
        """Generate a Sequence that is the intersection of an iterable with
        this Sequence.

        This is useful for determining which scout frames are valid
        """
        common_frames = set(self._iterable).intersection(set(iterable))
        if not common_frames:
            return None
        return Sequence.create(
            common_frames,
            chunk_size=self._chunk_size,
            chunk_strategy=self._chunk_strategy,
        )

    def union(self, iterable):
        """Generate a Sequence that is the union of an iterable with this
        Sequence.

        Useful for getting a sequence that covers multiple
        output ranges.
        """
        union_frames = set(self._iterable).union(set(iterable))

        return Sequence.create(
            union_frames,
            chunk_size=self._chunk_size,
            chunk_strategy=self._chunk_strategy,
        )

    def offset(self, value):
        """Generate a new Sequence with all values offset.

        It is an error if the new sequence would contain negative
        numbers.
        """
        offset_frames = [x + value for x in self._iterable]
        return Sequence.create(
            offset_frames,
            chunk_size=self._chunk_size,
            chunk_strategy=self._chunk_strategy,
        )

    def expand(self, template):
        """Expand a hash template with this sequence.

        Example /some/directory_###/image.#####.exr. Sequence is invalid
        if it contains no hashes. First we replace the hashes with a
        template placeholder that specifies the padding as a number.
        Then we use format to replace the placehoders with numbers.
        """
        if not re.compile("#+").search(template):
            raise ValueError("Template must contain hashes.")

        format_template = re.sub(
            r"(#+)", lambda match: "{{0:0{:d}d}}".format(len(match.group(1))), template
        )

        return [format_template.format(el) for el in self._iterable]

    def expand_format(self, *templates):
        result = []
        for f, template in zip(self._iterable, itertools.cycle(templates)):
            result.append(template.format(frame=f))
        return result

    def expand_dollar_f(self, *templates):
        """
        Expands $ templates such as those containing $3F or $F.

        If a single template is given, such as image.$2F.exr, and the sequence
        contains [1,2,4] then the result will be:
        [
            "image.01.exr",
            "image.02.exr",
            "image.04.exr"
        ]
        However, if there are 3 templates, such as:
        a_1/image.$2F.exr
        a_2/image.$2F.exr
        a_4/image.$2F.exr
        then the result will be:
        [
            a_1/image.01.exr,
            a_2/image.02.exr,
            a_4/image.04.exr
        ]
        i.e. there will always be len(sequence) elements in the result.

        The intention is that the number of templates given be either 1 or
        len(sequence), but for completeness, we cycle if there is some number
        between, and clip if there are too many.
        """
        result = []
        for f, template in zip(self._iterable, itertools.cycle(templates)):
            format_template = re.sub(
                r"\$(\d?)F",
                lambda match: "{{frame:0{:d}d}}".format(int(match.group(1) or 0)),
                template,
            )
            result.append(format_template.format(frame=f))
        return result

    def subsample(self, count):
        """Take a selection of elements from the sequence.

        Return value is a new sequence where the elements are plucked in
        the most distributed way.
        """
        n = len(self)
        count = _clamp(1, count, n)

        res = []
        gap = n / float(count)
        pos = gap / 2.0

        for _ in range(count):
            index = int(pos)
            res.append(self._iterable[index])
            pos += gap

        spec = ",".join([str(x) for x in res])
        return Sequence.create(spec)

    def best_chunk_size(self):
        """Determine the best distribution of frames per chunk based on the
        current number of chunks.

        For example, if chunk size is 70 and there are 100 frames, 2
        chunks will be generated with 70 and 30 frames. It would be
        better to have 50 frames per chunk and this method returns that
        number. NOTE: It doesn't make sense to use the best chunk size
        when chunk strategy is progressions.
        """
        count = int(math.ceil(len(self._iterable) / float(self._chunk_size)))
        return int(math.ceil(len(self._iterable) / float(count)))

    def is_progression(self):
        """Is this sequence a progression."""
        return isinstance(self, Progression)

    def to(self, range_sep, step_sep, block_sep):
        return (
            str(self)
            .replace("-", range_sep)
            .replace("x", step_sep)
            .replace(",", block_sep)
        )

    @property
    def chunk_size(self):
        """Return chunk size."""
        return self._chunk_size

    @chunk_size.setter
    def chunk_size(self, value):
        """Set chunk_size.

        Max is the length of frames and min is 1. If a value less than 1
        is given, set it to max, which means the default is to output 1
        chunk.
        """
        num = len(self._iterable)
        self._chunk_size = num if value < 1 else sorted([num, value])[0]

    @property
    def chunk_strategy(self):
        """Return the current strategy for emitting chunks."""
        return self._chunk_strategy

    @chunk_strategy.setter
    def chunk_strategy(self, value):
        """Set strategy for emitting chunks."""
        self._chunk_strategy = value

    def __iter__(self):
        return iter(self._iterable)

    def __len__(self):
        return len(self._iterable)

    def __str__(self):
        """String representation contains the stringified progressions."""
        progs = Progression.factory(self._iterable)
        return (",").join([str(p) for p in progs])

    def __repr__(self):
        """Repr contains whats necessary to recreate."""
        return "Sequence.create(%r)" % (str(self))


class Progression(Sequence):
    def __init__(self, start, end, step, **kw):
        self._iterable = xrange(start, end + 1, step)
        self.chunk_size = kw.get("chunk_size", -1)
        self._chunk_strategy = kw.get("chunk_strategy", "linear")

    @property
    def step(self):
        if self.start == self.end:
            return 1
        return self._iterable[1] - self._iterable[0]

    @property
    def range(self):
        return (self.start, self.end, self.step)

    def __str__(self):
        if self.start == self.end:
            return str(self.start)
        if self.step == 1:
            return "%s-%s" % (self.start, self.end)
        return "%s-%sx%s" % (self.start, self.end, self.step)

    @staticmethod
    def factory(iterable, **kw):
        """Split a sequence of integers into arithmetic progressions.

        This is not necessarily the most compact set of progressions in
        the sequence as that would take too long for large sets, and be
        really difficult to code. This algorithm walks through the
        sorted sequence, gathers elements with the same gap as the
        previous element. The max size keyword arg will limit the length
        of progressions.
        """
        max_size = kw.get("max_size", len(iterable))
        iterable = sorted(iterable)

        if max_size == 1:
            return [Sequence.create(prog) for prog in iterable]

        if max_size < 1:
            max_size = len(iterable)

        results = [[]]

        # add a sentinel to the end - see below
        iterable.append(-1)
        prog = 0
        for element in iterable:
            # if not adding to current progression, create a new progression.
            if not _should_add(element, results[prog], max_size):
                last_prog = prog
                prog += 1
                results.append([])

                # if the last progression only has 2 elements, then steal
                # the second of them to start this progression. Why? because
                # we are greedy and will have more chance of making longer
                # progressions if we dismantle progressions of length 2 and
                # then pair up the straggling singles later.
                # Note that the sentinel added above ensures this rule also
                # works on the original last element.
                if len(results[last_prog]) == 2:
                    results[prog].append(results[last_prog][1])
                    results[last_prog] = results[last_prog][:1]

            results[prog].append(element)

        # remove the sentinel from the last progression,
        # or remove the whole last
        # progression if it contains only the sentinel.
        if len(results[prog]) == 1:
            results = results[:-1]
        else:
            results[prog] = results[prog][:-1]

        # Now join straggling singles into pairs if possible. Loop
        # through the singles, joining every other one to the one
        # before. In theory we could recurse here - looking for
        # longer progressions in the stragglers.
        singles = []
        j = 0
        for i in range(len(results)):
            if len(results[j]) == 1:
                singles.append(results.pop(j)[0])
            else:
                j += 1

        for i, single in enumerate(singles):
            if i % 2 == 0:
                results.append([single])
            else:
                results[-1].append(single)

        results.sort(key=lambda v: v[0])

        return [Sequence.create(prg) for prg in results]


def _should_add(element, progression, max_size):
    """Should an element be added to a progression?

    Specifically, if the progression has 0 or 1 elements, then add it,
    as this starts the progression. Otherwise check if the gap between
    the element and the last in the progression is the same as the gap
    in the rest of the progression.
    """
    if len(progression) < 2:
        return True
    if len(progression) == max_size:
        return False
    return progression[1] - progression[0] == element - progression[-1]

