

import fnmatch

FILES = []


def populate(files):
    """Generate list of files from fixture data."""
    global FILES
    FILES = sorted(set(files))


def glob(pattern):
    return fnmatch.filter(FILES, pattern)
