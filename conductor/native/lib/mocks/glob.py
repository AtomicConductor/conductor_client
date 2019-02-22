import fnmatch
from conductor.native.lib.sequence import Sequence

FILES = []


def initialize(data):
    """Generate list of files from fixture data."""
    global FILES
    for item in data["files"]:
        if item.get("params"):
            for fn in Sequence.permutations(item["path"], **item["params"]):
                FILES.append(fn)
        else:
            FILES.append(item["path"])
    FILES = sorted(set(FILES))

def glob(pattern):
    return fnmatch.filter(FILES, pattern)
