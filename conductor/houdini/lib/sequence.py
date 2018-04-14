
import math
import re
import itertools

NUMBER_RE = re.compile(r"^(\d+)$")
RANGE_RE = re.compile(r"^(?:(\d+)-(\d+)(?:x(\d+))?)+$")


def _clamp(minval, val, maxval):
    """Clamp value to min and max."""
    return sorted([minval, val, maxval])[1]


def _resolve_start_end_step(*args):
    """Generate a valid start, end, step.

    Args may be individual ints or strings. Start may be
    after end. Step may be None or missing. Arg may be a
    single range string as 'start-endxstep' where end and
    step are optional.
    """
    if len(args) == 1:
        arg = str(args[0])
        number_match = NUMBER_RE.match(arg)
        range_match = RANGE_RE.match(arg)
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


def _to_frames(arg):
    """Convert frame spec to a sorted unique set of frames.

    Logic, If the arg has __iter__ it is not a string, but
    is iterable. If it is a string break it up into ranges
    to build the list of frames.
    """
    if hasattr(arg, "__iter__"):
        return sorted(set(arg))
    arg = str(arg)
    the_set = set()
    for part in [x.strip() for x in arg.split(',')]:
        number_matches = NUMBER_RE.match(part)
        if number_matches:
            vals = number_matches.groups()
            the_set.add(int(vals[0]))
        elif RANGE_RE.match(part):
            start, end, step = _resolve_start_end_step(part)
            the_set = the_set.union(xrange(start, end + 1, step))
        elif part:
            # There should be no other non-empty parts
            raise ValueError("Invalid frame spec")
    return sorted(the_set)


class Sequence(object):
    """A collection of frames with the ability to generate chunks."""

    @staticmethod
    def permutations(template, **kw):
        for vals in itertools.product(
                *(iter(Sequence.create(spec)) for spec in kw.values())):
            subs = dict(zip(kw, vals))
            yield template % subs

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

    @staticmethod
    def create(*args, **kw):
        """Factory which will create either a Sequence or a Progression.

        A Sequence is an arbitrary list of frames with
        unique sorted elements. A Progression, which is a
        subclass of Sequence, can be expressed as an
        arithmetic progression: i.e. start, end, step.
        """
        if len(args) == 0:
            raise TypeError("Sequence#create needs at least one arg")
        if len(args) > 1:
            # its a start, end, step - so return a Progression
            start, end, step = _resolve_start_end_step(*args)
            return Progression(start, end, step, **kw)
        frames = _to_frames(args[0])
        if not frames:
            raise TypeError("Can't create Sequence with no frames")

        if len(frames) == 1:
            return Progression(frames[0], frames[0], 1, **kw)
        step = frames[1] - frames[0]
        # if a frames can be expressed as a range, it is a progression
        if range(frames[0], frames[-1] + 1, step) == frames:
            return Progression(frames[0], frames[-1], step, **kw)
        return Sequence(frames, **kw)

    def __init__(self, iterable, **kw):
        """Instantiate from list of ints.

        This method will usually be called by a factory.
        """
        self._iterable = iterable
        self.chunk_size = kw.get("chunk_size", -1)
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

        Say we have 100 frames to render (1-100). With
        chunksize of 5, there will be 20 instances. The
        first chunk will render 1, 21, 41, 61 81, the second
        chunk 2, 22, 42, 62, 82 and so on, which means the
        artist will see frames 1,2,3,4...20 early on. This
        may be useful to check for frame coherence artifacts
        without waiting for a whole chunk to render on one
        machine.
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
                Sequence.create(
                    list(self._iterable)[i:i + self._chunk_size])
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
            return Progression.factory(
                self._iterable, max_size=self._chunk_size)
        return self._linear_chunks()

    def chunk_count(self):
        """Calculate the number of chunks that will be emitted.

        If strategy is progressions we just generate them
        and count the objects. Otherwise we can calculate
        from the frame length and chunk size directly
        """
        if self._chunk_strategy == "progressions":
            return len(
                Progression.factory(
                    self._iterable,
                    max_size=self._chunk_size))
        return int(math.ceil(len(self._iterable) / float(self._chunk_size)))

    def intersection(self, iterable):
        """Generate a Sequence that is the intersection of an iterable with
        this Sequence.

        This is useful for determining which scout frames
        are valid
        """
        common_frames = set(self._iterable).intersection(set(iterable))
        if not common_frames:
            return None
        return Sequence.create(common_frames)

    def subsample(self, count):
        """Take a selection of elements from the sequence.

        Return value is a new sequence.
        """
        n = len(self)
        count = sorted([1, count, n])[1]

        res = []
        gap = n / float(count)
        pos = gap / 2.0

        for i in range(count):
            index = int(pos)
            res.append(self._iterable[index])
            pos += gap

        spec = ",".join([str(x) for x in res])
        return Sequence.create(spec)

    def best_chunk_size(self):
        """Determine the best distribution of frames per chunk based on the
        current number of chunks.

        For example, if chunk size is 70 and there are 100
        frames, 2 chunks will be generated with 70 and 30
        frames. It would be better to have 50 frames per
        chunk and this method returns that number. NOTE: It
        doesn't make sense to use the best chunk size when
        chunk strategy is progressions.
        """
        count = int(math.ceil(len(self._iterable) / float(self._chunk_size)))
        return math.ceil(len(self._iterable) / float(count))

    def is_progression(self):
        """Is this sequence a progression."""
        return isinstance(self, Progression)

    @property
    def chunk_size(self):
        """Return chunk size."""
        return self._chunk_size

    @chunk_size.setter
    def chunk_size(self, value):
        """Set chunk_size.

        Max is the length of frames and min is 1. If a value
        less than 1 is given, set it to max, which means the
        default is to output 1 chunk.
        """
        n = len(self._iterable)
        self._chunk_size = n if value < 1 else sorted([n, value])[0]

    @property
    def chunk_strategy(self):
        """Return the current strategy for emitting chunks."""
        return self._chunk_strategy

    @chunk_size.setter
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
        return (',').join([str(p) for p in progs])

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

        This is not necessarily the most compact set of
        progressions in the sequence as that would take too
        long for large sets, and be really difficult to
        code. This algorithm walks through the sorted
        sequence, gathers elements with the same gap as the
        previous element. The max size keyword arg will
        limit the length of progressions.
        """
        max_size = kw.get("max_size", len(iterable))
        iterable = sorted(iterable)

        if max_size == 1:
            return [Sequence.create(p) for p in iterable]

        if max_size < 1:
            max_size = len(iterable)

        results = [[]]

        # add a sentinel to the end - see below
        iterable.append(-1)
        p = 0
        for element in iterable:
            # if not adding to current progression, create a new progression.
            if not _should_add(element, results[p], max_size):
                lastp = p
                p += 1
                results.append([])

                # if the last progression only has 2 elements, then steal
                # the second of them to start this progression. Why? because
                # we are greedy and will have more chance of making longer
                # progressions if we dismantle progressions of length 2 and
                # then pair up the straggling singles later.
                # Note that the sentinel added above ensures this rule also
                # works on the original last element.
                if len(results[lastp]) == 2:
                    results[p].append(results[lastp][1])
                    results[lastp] = results[lastp][:1]

            results[p].append(element)

        # remove the sentinel from the last progression, or remove the whole last
        # progression if it contains only the sentinel.
        if len(results[p]) == 1:
            results = results[:-1]
        else:
            results[p] = results[p][:-1]

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

        for i, s in enumerate(singles):
            if i % 2 == 0:
                results.append([s])
            else:
                results[-1].append(s)

        results.sort(key=lambda v: v[0])

        return [Sequence.create(p) for p in results]


def _should_add(element, progression, max_size):
    """Should an element be added to a progression?

    Specifically, if the progression has 0 or 1 elements,
    then add it, as this starts the progression. Otherwise
    check if the gap between the element and the last in the
    progression is the same as the gap in the rest of the
    progression.
    """
    if len(progression) < 2:
        return True
    if len(progression) == max_size:
        return False
    return progression[1] - progression[0] == element - progression[-1]
