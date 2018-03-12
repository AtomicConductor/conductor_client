"""Nothing expanded in __init__ No expansion in _get_tokens either."""


import hou
import json
from conductor.houdini.lib.sequence import Clump
from conductor.houdini.lib.expansion import Expander
from conductor.houdini.hda.task import Task
from conductor.houdini.hda import (
    frame_spec,
    software,
    render_source,
    notifications,
    dependency_scan)


class Job(object):
    """Prepare a Job."""

    def __init__(self, node):

  
        self._node = node
        self._sequence = frame_spec.main_frame_sequence(node)

        # will be none if not doing scout frames
        self._scout_sequence = frame_spec.resolved_scout_sequence(node)
        self._instance = self._get_instance()
    
        self._project = self._node.parm('project').eval()
     
        # self._take = hou.takes.currentTake()
        self._notifications = notifications.get_notifications(self._node)
         
        self._source_node = render_source.get_render_node(self._node)


    
        if not (self._source_node):
            raise hou.InvalidInput(
                "%s needs a connected source node." %
                self._node)
        self._tokens = self._collect_tokens()

    def dry_run(self, submission_tokens):
        """Build an object that fully describes the submission without mutating
        anything."""
        tokens = submission_tokens.copy()
        tokens.update(self._tokens)
        expander = Expander(**tokens)

        job = {
            "tokens": tokens,
            "metadata": expander.evaluate(self._node.parm("metadata").eval()),
            "title": expander.evaluate(self._node.parm("job_title").eval()),
            "scene_file": expander.evaluate(
                self._node.parm("scene_file").eval()),
            "node_name": self._node.name(),
            "dependencies": dependency_scan.fetch(self._sequence),
            "package_ids": software.get_chosen_ids(self._node),
            "environment": software.get_environment(self._node),
            "project": self._project,
            "source": self._source_node.path(),
            "type": self._source_node.type().name(),
            "notifications": self._notifications,
            "tasks": [],
        }

        for clump in self._sequence.clumps():
            task = Task(self._node, clump)
            job["tasks"].append(task.dry_run(tokens))

        return job

    def _project_name(self):
        projects = json.loads(self._node.parm('projects').eval())
        project_names = [project["name"]
                         for project in projects if project['id'] == self._project]
        if not project_names:
            raise hou.InvalidInput("%s invalid project." % self._node)
        return project_names[0]

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
        sorted_frames = sorted(self._sequence._frames)

        tokens = {}
        tokens["length"] = str(len(self._sequence))
        tokens["sequence"] = str(Clump.create(iter(self._sequence)))
        tokens["sequencemin"] = str(sorted_frames[0])
        tokens["sequencemax"] = str(sorted_frames[-1])
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
        tokens["project"] = self._project_name()
        tokens["submitter"] = self._node.name()
        tokens["source"] = self._source_node.path()
        tokens["type"] = self._source_node.type().name()
        return tokens
