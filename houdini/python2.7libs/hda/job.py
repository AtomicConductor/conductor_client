"""Nothing expanded in __init__ No expansion in _get_tokens either."""


import hou
import json
from sequence import Clump
from expansion import Expander
from task import Task
import frame_spec

import dependency_scan as deps



class Job(object):
    """Prepare a Job."""

    def __init__(self, node):
        self._node = node
        self._sequence = frame_spec.main_frame_sequence(node)

        # will be none if not doing scout frames
        self._scout_sequence = frame_spec.resolved_scout_sequence(node)
        self._instance = self._get_instance()
        self._take = hou.takes.currentTake()
        self._tokens = self._collect_tokens()

    def dry_run(self, submission_tokens):
        """Build an object that fully describes the submission without mutating
        anything."""
        tokens = submission_tokens.copy()
        tokens.update(self._tokens)
        expander =  Expander(**tokens)

        job = {
            "tokens": tokens,
            "metadata": expander.evaluate(self._node.parm("metadata").eval()),
            "title": expander.evaluate(self._node.parm("job_title").eval()),
            "scene_file": expander.evaluate(
                self._node.parm("scene_file").eval()),
            "take_name": self._take.name(),
            "dependencies": deps.fetch(self._sequence),
            "tasks": []
        }

        for clump in self._sequence.clumps():
            print repr(clump)
            task = Task(self._node, clump)
            job["tasks"].append(task.dry_run(tokens))




        return job

    def _get_instance(self):
        flavor, cores = self._node.parm(
            'machine_type').eval().split("_")
        machines = json.loads(self._node.parm('machine_types').eval())
        result = [machine for machine in machines if machine['cores'] ==
                  int(cores) and machine['flavor'] == flavor][0]

        result["preemptible"] = self._node.parm('preemptible').eval()
        result["retries"] = self._node.parm("retries").eval()
        return result

    def _collect_tokens(self):
        """Tokens are string kv pairs used for substitutions."""

        # print "-" * 30
        # print iter(self._scout_sequence)
        tokens = {}
        tokens["scene"] = self._take.name()
        tokens["take"] = self._take.name()
        tokens["length"] = str(len(self._sequence))
        tokens["sequence"] = str(Clump.create(iter(self._sequence)))
        # tokens["sequencestart"] = str(self._sequence[0])
        # tokens["sequenceend"] = str(self._sequence[-1])
        tokens["scout"] = "false"
        if self._scout_sequence:
            tokens["scout"] = (
                ",".join([str(x) for x in Clump.regular_clumps(self._scout_sequence)]))
        tokens["clumpsize"] = str(self._sequence.clump_size)
        tokens["clumpcount"] = str(self._sequence.clump_count())
        tokens["scoutcount"] = str(len(self._scout_sequence or []))
        tokens["instcores"] = str(self._instance.get("cores"))
        tokens["instflavor"] = self._instance.get("flavor")
        tokens["instance"] = self._instance.get("description")
        tokens["preemptible"] = "true" if self._instance.get(
            "preemptible") else "false"
        tokens["retries"] = str(self._instance.get("retries"))
        return tokens
 
