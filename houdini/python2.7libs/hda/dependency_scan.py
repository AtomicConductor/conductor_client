import glob
import re
import hou


def fetch(sequence):
    """Finds all file dependencies in the project for specific range of frames.

    Args:
      frame_begin: First frame (inclusive) of range to render.
      frame_end: Last frame (inclusive) of range to render.
      step: Frame range step.

    Returns:
      set of str, List of detected dependencies.

    """
    refs = hou.fileReferences()
    # frames = xrange(int(sequence), int(frame_end) + 1, int(step))

    result = set()

    wildcards = ['<udim>', '$SF']
    wildcard_regex = [re.compile(re.escape(wc), re.IGNORECASE)
                      for wc in wildcards]

    for frame in sequence:
        for parm, _ in refs:
            if parm:
                file_path = parm.evalAtFrame(frame)
                if file_path in result:
                    continue
                for wildcard in wildcard_regex:
                    file_path = wildcard.sub('*', file_path)
                for file in glob.glob(file_path):
                    try:
                        if hou.findFile(file) and file not in result:
                            result.add(file)
                    except hou.OperationFailed:
                        pass
    return result
