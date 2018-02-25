import hou
import hda


class Job(object):
    """Prepare a Job."""

    def __init__(self, node):
        self._node = node
        self._frames = hda.frame_spec.frame_set(node)

        self._clump_size = node.parm("clump_size").eval()
        self._scout_frames = hda.frame_spec.scout_frame_set(node) if node.parm(
            "do_scout").eval() else None
        self._instance_type = node.parm('machine_type').eval()
        self._preemptible = node.parm('preemptible').eval()
        self._retries = node.parm('retries').eval()
        self._metadata = node.parm('metadata').eval()
        self._software = node.parm('software').eval()
        self._scene_file = node.parm('scene_file').eval()
        self._take_name = hou.takes.currentTake()

    def data(self):
        result = {
            "frames": self._frames,
            "clump_size": self._clump_size,
            "scout_frames": self._scout_frames,
            "instance_type": self._instance_type,
            "preemptible": self._preemptible,
            "retries": self._retries,
            "metadata": self._metadata,
            "software": self._software,
            "scene_file": self._scene_file,
            "take_name":  self._take_name
        }
        return result

    def generate_tasks():
        pass
        
