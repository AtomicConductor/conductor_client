
import os
import re
from itertools import takewhile
import glob

from conductor.native.lib.gpath import Path

GLOBBABLE_REGEX = re.compile(r'\*|\?|\[')


class PathList(object):
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

    def add(self, *paths):
        """Add one or more files.

        Duplicate files and directories that contain other files may be
        added and no deduplication will happen at this time.
        """
        for path in paths:
            self._add_one(path)

    def _add_one(self, path):
        """Add a single file.

        Note that when an element is added, it may cause the list to
        change next time it is deduplicated, which includes getting
        shorter. This could happen if a containing directory is added.
        Therefore we have to set the peg position to zero.
        """
        # print "isinstance(path, Path) ", isinstance(path, Path)
        if not type(path).__name__ == "Path":

            # if not isinstance(path, Path):
            path = Path(path)
            # print "PATH IS NOT A Path"
        # else:
            # print "PATH IS A Path"
        # print "PATH: ", path.posix_path()
        self._entries.append(path)
        self._clean = False
        self._current = 0

    def _deduplicate(self):
        """Deduplicate if it has become dirty.

        Algorithm explained at:
        https://stackoverflow.com/questions/49478361 .
        """
        if self._clean:
            return

        sorted_entries = sorted(
            self._entries, key=lambda entry: (entry.depth, -len(entry.tail)))

        self._entries = []
        for entry in sorted_entries:
            if any(entry.startswith(p) for p in self._entries):
                continue
            self._entries.append(entry)
        self._clean = True

    def __contains__(self, key):
        if not isinstance(key, Path):
            key = Path(key)
        return key in self._entries

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
        the case of a single file we return it AS-IS and the caller can
        then stat to find out for sure.

        If no files exist return None.

        If the filesystem root is the common path, return root path, which is
        not entirely correct on windows with drive letters.
        """
        if not self._entries:
            return None

        def _all_the_same(rhs):
            return all(n == rhs[0] for n in rhs[1:])

        levels = zip(*[p.all_components for p in self._entries])

        common = [x[0] for x in takewhile(_all_the_same, levels)]
        return Path(common or "/")

    def glob(self):
        """Glob expansion for entries containing globbable characters.

        We don't simply glob every entry since that would remove entries
        that don't yet exist. And we can't just rely on zero glob
        results because it may have been a legitimate zero result if it
        was globbable but matched nothing. So we test for glob
        characters (*|?|[) to determine whether to attempt a glob.
        """
        self._deduplicate()
        result = []
        for entry in self._entries:
            pp = entry.posix_path()
            if GLOBBABLE_REGEX.search(pp):
                globs = glob.glob(entry.posix_path())
                result += globs
            else:
                result.append(pp)
        self._entries = [Path(g) for g in result]
        self._clean = False
        self._current = 0

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
