"""Nothing expanded in __init__ No expansion in _get_tokens either."""


import hou
import hda
import json


class Job(object):
    """Prepare a Job."""

    def __init__(self, node):
        self._node = node
        self._sequence = hda.frame_spec.main_frame_sequence(node)
        self._scout_sequence = hda.frame_spec.resolved_scout_sequence(node)
        self._instance = self._get_instance()
        self._take = hou.takes.currentTake()
        self._tokens = self._collect_tokens()

    def dry_run(self, submission_tokens):
        """Build an object that fully describes the submission without mutating
        anything."""
        tokens = submission_tokens.copy()
        tokens.update(self._tokens)
        expander = hda.expansion.Expander(**tokens)

        job = {}
        job["tokens"] = self._tokens
        job["metadata"] = expander.evaluate(
            self._node.parm("metadata").eval())

        scene_file_temp =  self._node.parm("scene_file").eval()


        job["scene_file"] = expander.evaluate(scene_file_temp)
        
        print scene_file_temp
        print tokens
        print  "SCENE FILE %s" % job["scene_file"]



        return job

    def _get_instance(self):
        flavor, cores = self._node.parm(
            'machine_type').eval().split("_")
        machines = json.loads(self._node.parm('machine_types').eval())
        result = [machine for machine in machines if machine['cores'] == int(cores) and machine['flavor'] == flavor][0]
 
        result["preemptible"] = self._node.parm('preemptible').eval()
        result["retries"] = self._node.parm("retries").eval()
        return result

    def _collect_tokens(self):
        """Tokens are string kv pairs used for substitutions."""
        tokens = {}
        tokens["take"] = self._take.name()
        tokens["length"] = len(self._sequence)
        tokens["clumpsize"] = self._sequence.clump_size
        tokens["clumpcount"] = self._sequence.clump_count()
        tokens["scoutcount"] = len(self._scout_sequence or [])
        tokens["instcores"] = self._instance.get("cores")
        tokens["instflavor"] = self._instance.get("flavor")
        tokens["instdesc"] = self._instance.get("description")
        tokens["preemptible"] = "preemptible" if self._instance.get(
            "preemptible") else "not preemptible"
        tokens["retries"] = self._instance.get("retries")
        return tokens

    def generate_tasks():
        pass
