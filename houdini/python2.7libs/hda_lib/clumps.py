import re
import math


class Clump(object):

    '''A Clump is a wrapper around an iterable of frames

     it can generate a list of filenames with numbers substituted'''

    def __init__(self):
        self._iterable = None

    def __len__(self):
        return len(self._iterable)

    def __iter__(self):
        return iter(self._iterable)

    @property
    def regular(self):
        """one_line_doc_string."""
        return isinstance(self, RegularClump)

    @property
    def irregular(self):
        """one_line_doc_string."""
        return isinstance(self, IrregularClump)

    def format(self, format_string):
        '''Insert each frameNumber in a string

        For example if format string is "foo/%02d/fn.%04d.ass"
        Then the result array will contain:
        "foo/01/fn.0001.ass"
        "foo/02/fn.0002.ass"
        and so on'''
        num_subs = format_string.count('%')
        arr = []
        for i in self._iterable:
            substitutions = tuple([i] * num_subs)
            arr.append(format_string % substitutions)
        return arr

    def expand(self):
        '''return all frames as string'''
        return ",".join(['%s' % x for x in self._iterable])

    def compact_frames(self):
        """one_line_doc_string."""
        print 'must implement compact_frames'
        raise NotImplementedError


class RegularClump(Clump):

    '''A RegularClump holds an xrange

    It has inclusive upper bound.
    It will print itself as "1:10x2"'''

    def __init__(self, start, end, step=1):
        """one_line_doc_string."""
        Clump.__init__(self)

        if start > end:
            start, end = end, start
        if step < 1:
            step = 1
        self.start = start
        self.end = end
        self.step = step
        self._iterable = xrange(start, end + 1, step)

    def compact_frames(self):
        return "%s,%s,%s" % (self.start, self.end, self.step)

    def __str__(self):
        return "%s-%sx%s" % (self.start, self.end, self.step)


class IrregularClump(Clump):

    '''An irregularClump holds a frame list

    It will print itself as "1, 3, 4, 9, 6..." unless
    its longer than 6 elements, in which case it will
    be truncated "first ~irregular~ last"

    Full list can be created as a single comma delimited
    string with expand()'''

    def __init__(self, frames):
        """one_line_doc_string."""
        Clump.__init__(self)
        self._iterable = list(frames)

    def compact_frames(self):
        return "%s" % self.expand()

    def __str__(self):
        if len(self._iterable) > 6:
            return "%s ~irregular~ %s" % (self._iterable[0],
                                          self._iterable[-1])
        return ", ".join([str(x) for x in self._iterable])

    @property
    def frames(self):
        """one_line_doc_string."""
        return self._iterable


class ClumpCollection(object):
    """one_line_doc_string."""

    def __init__(self, **kwargs):
        '''Two ways a ClumpCollection can be initiated

        ClumpCollection(start=, end=, step=, clumpSize=, cycle=)
        ClumpCollection(frameList=, clumpSize=)
        '''
        self._clump_size = max(1, kwargs.get('clumpSize', 1))
        self._clumps = []
        if 'frameList' in kwargs:
            # potentially irregular clumps
            self._generate_clumps_from_string(kwargs['frameList'])
        else:
            # definitely regular clumps
            start = kwargs.get('start', 1)
            end = kwargs.get('end', start)
            if start > end:
                start, end = (end, start)

            step = max(1, kwargs.get('step', 1))
            cycle = kwargs.get('cycle', False)
            if cycle:
                self._generate_cycle_clumps(start, end, step)
            else:
                self._generate_linear_clumps(start, end, step)

    @property
    def clumps(self):
        """one_line_doc_string."""
        return self._clumps

    def _generate_clumps_from_string(self, frameListString):
        """one_line_doc_string."""
        frame_list = []

        frame_regex = re.compile(r'^\s*([0-9.]+)\s*$')
        range_regex = re.compile(r'^\s*([0-9.]+)\s*\-\s*([0-9.]+)\s*$')
        step_regex = re.compile(
            r'^\s*([0-9.]+)\s*\-\s*([0-9.]+)\s*x\s*([0-9.]+)\s*$')

        for frame_group in frameListString.split(','):
            # single frame
            match = frame_regex.match(frame_group)
            if match:
                frame_list.append(int(float(match.group(1))))
                continue
            # frame range
            match = range_regex.match(frame_group)
            if match:
                start_frame = int(float(match.group(1)))
                end_frame = int(float(match.group(2)))
                frame_list.extend(range(start_frame, end_frame + 1))
                continue
            # frame range with step
            match = step_regex.match(frame_group)
            if match:
                start_frame = int(float(match.group(1)))
                end_frame = int(float(match.group(2)))
                step = max(1, int(float(match.group(3))))
                frame_list.extend(range(start_frame, end_frame + 1, step))
                continue

        # uniquify, maintaining order
        seen = set()
        seen_add = seen.add
        frame_list = [x for x in frame_list if x not in seen and not seen_add(x)]

        # convert list(int)s into clumps
        # We travel along the list, chopping out slices
        # we make clump (derivitives) from the slices and append them.
        for start_idx in range(0, len(frame_list), self._clump_size):
            last_idx = start_idx + self._clump_size
            clump = self._clumpFromList(frame_list[start_idx:last_idx])
            self._clumps.append(clump)

    def _generate_linear_clumps(self, start, end, step):
        """one_line_doc_string."""
        start = int(start)
        end = int(end)
        step = int(step)

        gen = xrange(start, end + 1, step)
        num = len(gen)
        for start_idx in xrange(0, num, self._clump_size):
            last_idx = min(start_idx + (self._clump_size - 1), num - 1)
            clump = RegularClump(gen[start_idx], gen[last_idx], step)
            self._clumps.append(clump)

    def _generate_cycle_clumps(self, start, end, step):
        '''Render spread of frames.

        Say we have (1-200x2), thats 100 frames to render,
        but we only have 10 boxes. using cycleClumps, and
        setting clumpsize to 10, the first clump will render
        1,21,41 ... 181 which means the artist will see
        early on, a selection of frames spread throughout
        the animation.
        '''
        start = int(start)
        end = int(end + 1)
        step = int(step)

        gen = xrange(start, end, step)
        num = len(gen)
        nclumps = int(math.ceil(num / float(self._clump_size)))
        gap = step * nclumps
        for i in xrange(0, nclumps):
            istart = int(start + (i * step))
            iend = int(end)
            igap = int(gap)
            repeats = ((iend - 1) - istart) / igap
            if not repeats:
                igap = 1
            iend = istart + (repeats * igap)
            clump = RegularClump(istart, iend, igap)
            self._clumps.append(clump)

    def _clumpFromList(self, frame_list):
        '''Return regular or irregular clump

        If frame_list is equal to a range made from
        first element, last element, and gap between
        first and second element,
        then the clump is regular - which means
        it is in ascending order and has the same gap
        between consecutive elements
        '''

        if len(frame_list) == 1:
            return RegularClump(frame_list[0], frame_list[0])

        step = frame_list[1] - frame_list[0]
        if step < 0:
            return IrregularClump(frame_list)

        if len(frame_list) == 2:
            return RegularClump(frame_list[0], frame_list[1], step)

        regular_range = range(frame_list[0], frame_list[-1] + 1, step)
        if regular_range == frame_list:
            return RegularClump(frame_list[0], frame_list[-1], step)
        else:
            return IrregularClump(frame_list)

    def __iter__(self):
        return iter(self._clumps)

    def __len__(self):
        return len(self._clumps)

    def __str__(self):
        return ('\n').join(str(clump) for clump in self._clumps)

    @property
    def total_length(self):
        '''Sum of frames in all clumps'''
        count = 0
        for clump in self._clumps:
            count += len(clump)
        return count
