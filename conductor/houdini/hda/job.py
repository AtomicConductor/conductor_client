"""Nothing expanded in __init__ No expansion in _get_tokens either."""
import os

import hou
import json
from conductor.houdini.lib import data_block
from conductor.houdini.lib.sequence.clump import Clump
from conductor.houdini.hda.task import Task
from conductor.houdini.hda import (
    frame_spec_ui,
    software_ui,
    driver_ui,
    dependency_scan)

OUTPUT_DIR_PARMS = {
    "ifd": "vm_picture",
    "arnold": "ar_picture",
    "ris": "ri_display",
    "dop": "dopoutput",
    "geometry": 'sopoutput'
}


class Job(object):
    """Prepare a Job."""

    def __init__(self, node, parent_tokens, scene_file):

        self._node = node
        self._sequence = frame_spec_ui.main_frame_sequence(node)

        # will be none if not doing scout frames
        self._scout_sequence = frame_spec_ui.resolved_scout_sequence(node)
        self._instance = self._get_instance()

        self._source_node = driver_ui.get_driver_node(self._node)
        self._source_type = driver_ui.get_driver_type(self._node)

        if not (self._source_node):
            raise hou.InvalidInput(
                "%s needs a connected source node." %
                self._node.name())

        self._dependencies = dependency_scan.fetch(self._sequence)
        self._dependencies.append(scene_file)
        self._package_ids = software_ui.get_chosen_ids(self._node)
        self._environment = software_ui.get_environment(self._node).env

        self._tokens = self._collect_tokens(parent_tokens)

        self._task_command = self._node.parm("task_command").unexpandedString()

        self._title = self._node.parm("job_title").eval()

        self._output_directory = self._get_output_dir()

        self._metadata = self._node.parm("metadata").eval()

        self._tasks = []

        for clump in self._sequence.clumps():
            task = Task(clump, self._task_command, self._tokens)
            self._tasks.append(task)

    def _get_output_dir(self):
        result = os.path.join(hou.getenv("JOB"), "render")
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

    def _get_instance(self):
        flavor, cores = self._node.parm(
            'machine_type').eval().split("_")

        instance_types = data_block.ConductorDataBlock(
            product="houdini").instance_types()

        result = [it for it in instance_types if it['cores'] ==
                  int(cores) and it['flavor'] == flavor][0]
        result["preemptible"] = bool(self._node.parm('preemptible').eval())
        result["retries"] = self._node.parm("retries").eval()
        return result

    def _collect_tokens(self, parent_tokens):
        """Tokens are string kv pairs used for substitutions."""

        # tokens = parent_tokens.copy()
        tokens = {}
        sorted_frames = sorted(self._sequence._frames)
        tokens["CT_LENGTH"] = str(len(self._sequence))
        tokens["CT_SEQUENCE"] = str(Clump.create(iter(self._sequence)))
        tokens["CT_SEQUENCEMIN"] = str(sorted_frames[0])
        tokens["CT_SEQUENCEMAX"] = str(sorted_frames[-1])
        tokens["CT_SCOUT"] = ",".join(
            [str(x) for x in Clump.regular_clumps(self._scout_sequence or [])])
        tokens["CT_CLUMPSIZE"] = str(self._sequence.clump_size)
        tokens["CT_CLUMPCOUNT"] = str(self._sequence.clump_count())
        tokens["CT_SCOUTCOUNT"] = str(len(self._scout_sequence or []))
        tokens["CT_CORES"] = str(self._instance.get("cores"))
        tokens["CT_FLAVOR"] = self._instance.get("flavor")
        tokens["CT_INSTANCE"] = self._instance.get("description")
        tokens["CT_PREEMPTIBLE"] = "0" if self._instance.get(
            "preemptible") else "1"
        tokens["CT_RETRIES"] = str(self._instance.get("retries", 0))
        tokens["CT_JOB"] = self.node_name
        tokens["CT_SOURCE"] = self.source_path
        tokens["CT_TYPE"] = self.source_type

        for token in tokens:
            hou.putenv(token, tokens[token])
        tokens.update(parent_tokens)

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
        result["output_path"] = self._output_directory
        result["chunk_size"] = self._sequence.clump_size
        result["machine_type"] = self._instance.get("flavor")
        result["cores"] = self._instance.get("cores")
        result["tasks_data"] = [task.remote_data() for task in self._tasks]
        result["job_title"] = self._title
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


# class SimJob(Job):

#     def __init__(self, node, parent_tokens, scene_file):
#          super(SimJob,self).__init__(node, parent_tokens, scene_file)

      
#         self._source_node = driver_ui.get_driver_node(self._node)
#         self._source_type = driver_ui.get_driver_type(self._node)


#         self._sequence = 

#         # will be none if not doing scout frames
#         self._scout_sequence = frame_spec_ui.resolved_scout_sequence(node)
#         self._instance = self._get_instance()

#         if not (self._source_node):
#             raise hou.InvalidInput(
#                 "%s needs a connected source node." %
#                 self._node.name())

#         self._dependencies = dependency_scan.fetch(self._sequence)
#         self._dependencies.append(scene_file)
#         self._package_ids = software_ui.get_chosen_ids(self._node)
#         self._environment = software_ui.get_environment(self._node).env

#         self._tokens = self._collect_tokens(parent_tokens)

#         self._task_command = self._node.parm("task_command").unexpandedString()

#         self._title = self._node.parm("job_title").eval()

#         self._output_directory = self._get_output_dir()

#         self._metadata = self._node.parm("metadata").eval()

#         self._tasks = []

#         for clump in self._sequence.clumps():
#             task = Task(clump, self._task_command, self._tokens)
#             self._tasks.append(task)
