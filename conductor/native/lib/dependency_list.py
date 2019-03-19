
import os
import random
from itertools import takewhile


class DependencyList(object):
    """A list of files with lazy deduplication.

    Every time the private entrylist is accessed with an accessor such
    as len or iter, the _clean flag is checked. If it's dirty we
    deduplicate and set it clean. It becomes dirty again if files are
    added. Since adding a single directory can cause many contained
    files to be removed during deduplication, we set the next iterator
    to zero.
    """

    def __init__(self):
        """Initialize."""
        self._entries = []
        self._clean = False
        self._current = 0

    def add(self, *files, **kw):
        """Add one or more files.

        Files will be added according to the must_exist check. Duplicate
        files and directories that contain other files may be added and
        no deduplication will happen at this time.
        """
        must_exist = kw.get("must_exist", True)
        for f in files:
            self._add_a_file(f, must_exist)

    def _deduplicate(self):
        """Deduplicate if it has become dirty.

        Algorithm explained at:
        https://stackoverflow.com/questions/49478361 .
        """
        if self._clean:
            return

        sorted_entries = sorted(
            self._entries, key=lambda entry: (
                entry.count(
                    os.sep), -len(entry)))
        self._entries = []
        for entry in sorted_entries:
            if any(entry.startswith(p) for p in self._entries):
                continue
            self._entries.append(entry)
        self._clean = True

    def _add_a_file(self, f, must_exist):
        """Add a single file.

        If necessary, expand the user, expand env vars, and get the abs
        path. Note that when an element is added, it may cause the list
        to change next time it is deduplicated, which includes getting
        shorter. This could happen if a containing directory is added.
        Therefore we have to set the peg position to zero.
        """
        f = os.path.abspath(
            os.path.expanduser(
                os.path.expandvars(f)))
        if not must_exist or os.path.exists(f):
            self._entries.append(f)
            self._clean = False
        self._current = 0

    def common_path(self):
        """Find the common path among entries.

        This is useful for determining output directory when many
        renders are rendering to different places.

        In the case where
        only single path exists, it is not possible to tell from its
        name whether it is a file or directory. We don't want this
        method to touch the filesystem, that should be someone else's
        problem. A trailing slash would be a hint, but the absence of a
        trailing slash does not mean its a regular file. Therefore, in
        the case of a single file we return it ASIS and the caller can
        then stat to find out for sure.

        If no files exist return None.

        If the filesystem root is the common path, return os.sep.
        """
        if not len(self._entries):
            return None

        def _all_the_same(rhs):
            return all(n == rhs[0] for n in rhs[1:])
        levels = zip(*[p.split(os.sep) for p in self._entries])
        return os.sep.join(
            x[0] for x in takewhile(
                _all_the_same,
                levels)) or os.sep

    def __iter__(self):
        """Get an iterator to entries.

        Deduplicate just in time.
        """
        self._deduplicate()
        return iter(self._entries)

    def next(self):
        """Get the next element.

        Deduplicate just in time.
        """
        self._deduplicate()
        if self._current >= len(self._entries):
            raise StopIteration
        else:
            prev = self._current
            self._current += 1
            return self._entries[prev]

    def __len__(self):
        """Get the size of the entry list.

        Deduplicate just in time.
        """
        self._deduplicate()
        return len(self._entries)
