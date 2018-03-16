import hou
import re
import os
# Catch a timestamp of the form 2018_02_27_10_59_47 with optional
# underscore delimiters at the start and/or end of a string
TIMESTAMP_RE = re.compile(r"^[\d]{4}(_[\d]{2}){5}_*|_*[\d]{4}(_[\d]{2}){5}$")


def stripped_hip():
    """Strip off the extension and timestamp from start or end."""
    no_ext = re.sub('\.hip$', '', hou.hipFile.basename())
    return re.sub(TIMESTAMP_RE, '', no_ext)


def scene_name_to_use(node, timestamp="YYYY_MM_DD_hh_mm_ss"):
    if node.parm("use_timestamped_scene").eval():
        stripped = stripped_hip()
        path = os.path.dirname(hou.hipFile.name())
        scene = os.path.join(path,  "%s_%s.hip" % (stripped, timestamp) )
    else:
        scene = hou.hipFile.name()
 
    node.parm("scene_file").set(scene)
    return scene


def update(node):
    node.parm("scene_name").set(scene_name_to_use(node))


def get_extra_env_vars(node):
    num = node.parm("environment_kv_pairs").eval()
    result = []
    for i in range(1, num + 1):
        is_exclusive = node.parm("env_excl_%d" % i).eval()
        result.append({
            "name": node.parm("env_key_%d" % i).eval(),
            "value": node.parm("env_value_%d" % i).eval(),
            "merge_policy": ["append", "exclusive"][is_exclusive]
        })
    return result

