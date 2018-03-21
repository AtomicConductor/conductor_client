"""Nothing expanded in __init__ No expansion in _get_tokens either."""
import os

import hou
import json
from conductor.houdini.lib.sequence import Clump
from conductor.houdini.lib.expansion import Expander
from conductor.houdini.hda.task import Task
from conductor.houdini.hda import (
    frame_spec_ui,
    software_ui,
    render_source_ui,
    dependency_scan)

OUTPUT_DIR_PARMS = {
    "ifd": "vm_picture",
    "arnold": "ar_picture",
    "ris":  "ri_display"
}

class Job(object):
    """Prepare a Job."""

    def __init__(self, node, parent_tokens, scene_file):

        self._node = node
        self._sequence = frame_spec_ui.main_frame_sequence(node)

        # will be none if not doing scout frames
        self._scout_sequence = frame_spec_ui.resolved_scout_sequence(node)
        self._instance = self._get_instance()
 
        self._source_node = render_source_ui.get_render_node(self._node)
        self._source_type =  render_source_ui.get_render_type(self._node)

        if not (self._source_node):
            raise hou.InvalidInput(
                "%s needs a connected source node." %
                self._node.name())

        self._dependencies = dependency_scan.fetch(self._sequence)
        self._dependencies.append(scene_file)
        self._package_ids = software_ui.get_chosen_ids(self._node)
        self._environment = self._get_environment()
     
        self._tokens = self._collect_tokens(parent_tokens)
        self._task_command = self._node.parm("task_command").eval()

        expander = Expander(**self._tokens)

        self._title = expander.evaluate(self._node.parm("job_title").eval())

        out_dir = self._get_output_dir()
        self._output_directory =  expander.evaluate(out_dir) 

        self._metadata = expander.evaluate(
            self._node.parm("metadata").eval())

        self._tasks = []

        for clump in self._sequence.clumps():
            task = Task(clump, self._task_command, self._tokens)
            self._tasks.append(task)

    def _get_output_dir(self):
        result = os.path.join(  hou.getenv("JOB"), "render")
        if self._node.parm('override_output_dir').eval():
            ov_dir = self._node.parm('output_directory').eval()
            if ov_dir:
                result = ov_dir

        else:
            # try to get from the source node
            parm_name = OUTPUT_DIR_PARMS.get(self._source_type)
            if parm_name:
                path = self._source_node.parm(parm_name).eval()
                ov_dir = os.path.dirname(path)
                if ov_dir:
                    result = ov_dir
        return result



    def _get_environment(self):
        package_environment = software_ui.get_environment(self._node)
        extra_vars = software_ui.get_extra_env_vars(self._node)
        package_environment.extend(extra_vars)
        return package_environment.env

    def _get_instance(self):
        flavor, cores = self._node.parm(
            'machine_type').eval().split("_")
        machines = json.loads(self._node.parm('machine_types').eval())
        result = [machine for machine in machines if machine['cores'] ==
                  int(cores) and machine['flavor'] == flavor][0]

        result["preemptible"] = bool(self._node.parm('preemptible').eval())
        result["retries"] = self._node.parm("retries").eval()
        return result


    def _collect_tokens(self, parent_tokens):
        """Tokens are string kv pairs used for substitutions."""

        tokens = parent_tokens.copy()

        sorted_frames = sorted(self._sequence._frames)
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
        tokens["retries"] = str(self._instance.get("retries", 0))

        tokens["job"] = self.node_name
        tokens["source"] = self.source_path
        tokens["type"] = self.source_type
        return tokens

    def remote_args(self):
        result = {}

        result["upload_paths"] = self._dependencies
        result["autoretry_policy"] = {'preempted': {
            'max_retries': self._instance["retries"]}
        } if self._instance["preemptible"] else {}
        result["software_package_ids"] = self._package_ids
        result["preemptible"] = self._instance["preemptible"] 
        result["environment"] = self._environment
        result["enforced_md5s"] = {}
        result["scout_frames"] = ", ".join(self._scout_sequence or [])
        result["output_path"] =  self._output_directory
        result["chunk_size"] = self._sequence.clump_size
        result["machine_type"] = self._instance.get("flavor")
        result["cores"] = self._instance.get("cores")
        result["tasks_data"] = [task.remote_data() for task in self._tasks]
        result["job_title"] =  self._title
        result["metadata"] = self._metadata
        result["priority"] = 5
        result["max_instances"] = 0
        return result


    @property
    def node_name(self):
        return self._node.name()

    @property
    def title(self):
        return self._title

    @property
    def metadata(self):
        return self._metadata

    @property
    def output_directory(self):
        return self._output_directory

    @property
    def source_path(self):
        return self._source_node.path()

    @property
    def source_type(self):
        return self._source_type


    @property
    def dependencies(self):
        return self._dependencies

    @property
    def package_ids(self):
        return self._package_ids

    @property
    def environment(self):
        return self._environment

    @property
    def tokens(self):
        return self._tokens

    @property
    def tasks(self):
        return self._tasks
