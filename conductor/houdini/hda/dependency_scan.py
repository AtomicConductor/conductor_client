import glob
import re
import hou


def fetch(sequence):
    """Finds all file dependencies in the project.

    The results contain files that exist in the frame range,
    and files in te whitelisted parms. For example, the
    scene file may not exist, but we want to show that it is
    a dependency as it will presumably exist when a
    submission is uploaded.

    """

    refs = hou.fileReferences()
    result = set()

    whitelist_parms = ["scene_file"]
    for parm, _ in refs:
        if parm and parm.name() in whitelist_parms:
            file = parm.eval()
            if file:
                result.add(file)

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
                        if hou.findFile(file):
                            result.add(file)
                    except hou.OperationFailed:
                        pass

    return list(result)
