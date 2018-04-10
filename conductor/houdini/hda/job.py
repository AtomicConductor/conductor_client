"""Build an object to represent a Conductor job.
"""

import os

import hou
from conductor.houdini.hda import (dependency_scan, driver_ui, frame_spec_ui,
                                   software_ui)
from conductor.houdini.hda.task import Task
from conductor.houdini.lib import data_block
from conductor.houdini.lib.sequence import Sequence


class Job(object):
    """class Job holds all data for one Conductor job.

    Jobs are contained by a Submission and a Job contains
    potentially many Tasks. Like a Submission, it also
    manages a list of environment tokens that the user can
    access as $ variables.

    A regular Job is useful for simulations or other processes
    where it doesn't make sense to split the job into time
    based chunks. A ChunkedJob is a subclass, of Job. A
    chunked job makes use of the frame range specification in
    the UI to calculate how to manufacture a Task for each
    chunk.  A factory method is used to figure out if the job
    should be a Job or a ChunkedJob.
    """
    @staticmethod
    def create(node, tokens, scene):
        """Factory makes a Job or ChunkedJob.

        ChunkedJob makes a task per chunk. Job makes one
        task representing the whole time range.
        """
        if driver_ui.is_simulation(driver_ui.get_driver_type(node)):
            return Job(node, tokens, scene)
        return ChunkedJob(node, tokens, scene)

    def __init__(self, node, parent_tokens, scene_file):
        """Build the common job member data in this base class.

        * Get the driver node and type.
        * Get the instance type, retries, and preemptible flag.
        * Get the sequence.
        * Fetch dependencies, append scene file (which may not exist).
        * Get the Conductor package IDs and environment.
        * Get the task command, which will be expanded later per-chunk

        After _setenv has been called, the Job level token variables are
        valid and calls to eval string attributes will correctly resolve
        where those tokens have been used.  This is why we eval title,
        out_directory, metadata, and tasks after the call to _setenv()

        Notes about scene_file. We could have omitted to pass the scene
        file as an arg, and instead used the scene file contained in the
        tokens from the parent (CT_SCENE). The reason for not doing so
        is that tokens are intended for use as variables by the user
        only. So passing it separately signals that it is needed to
        construct the job proper. Specifically, it is needed to append
        to the dependency list as it is not picked up automatically by
        the dependency scan.
        """

        self._node = node
        self._tasks = []

        self._source = {
            "node": driver_ui.get_driver_node(self._node),
            "type": driver_ui.get_driver_type(self._node)
        }
        self._instance = self._get_instance()
        self._sequence = self._get_sequence()
        self._resources = self._get_resources(scene_file)

        self._tokens = self._setenv(parent_tokens)

        self._title = self._node.parm("job_title").eval()
        self._output_directory =  self._node.parm('output_directory').eval()
        self._metadata = self._node.parm("metadata").eval()

        task_command = self._node.parm("task_command").unexpandedString()
        for chunk in self._sequence["main"].chunks():
            task = Task(chunk, task_command, self._tokens)
            self._tasks.append(task)

    def _get_resources(self, scene_file):
        """Collect dependencies and environment.

        Dependency scan needs the sequence so that it scans
        only the frame range we are using.
        """
        dependencies = dependency_scan.fetch(
            self._node, self._sequence["main"])
        dependencies.append(scene_file)

        return {
            "package_ids": software_ui.get_chosen_ids(self._node),
            "environment": software_ui.get_environment(self._node),
            "dependencies": dependencies
        }
 

    def _get_instance(self):
        """Get everything related to the instance.

        Get the machine type, preemptible flag, and number
        of retries if preemptible. We use the key from the
        instance_type menu and look up the machine spec in
        the shared data where the full list of
        instance_types is stored.
        """
        result = {
            "preemptible": bool(self._node.parm('preemptible').eval()),
            "retries": self._node.parm("retries").eval()
        }
        flavor, cores = self._node.parm(
            'machine_type').eval().split("_")

        instance_types = data_block.for_houdini().instance_types()
        found = [it for it in instance_types if it['cores'] ==
                 int(cores) and it['flavor'] == flavor]
        if found:
            result.update(found[0])

        return result

    def _setenv(self, parent_tokens):
        """Env tokens common for all Job types.

        First we collect up token values for the job and set
        the env to those values. Then we merge with tokens
        from the parent so that in the preview display the
        user can see all tokens available at the Job level,
        including those that were set at the submitter
        level.
        """
        tokens = {}
        seq = self._sequence["main"]
        tokens["CT_SEQLENGTH"] = str(len(seq))
        tokens["CT_SEQUENCE"] = str(seq)
        tokens["CT_SEQUENCEMIN"] = str(seq.start)
        tokens["CT_SEQUENCEMAX"] = str(seq.end)
        tokens["CT_CORES"] = str(self._instance["cores"])
        tokens["CT_FLAVOR"] = self._instance["flavor"]
        tokens["CT_INSTANCE"] = self._instance["description"]
        tokens["CT_PREEMPTIBLE"] = "preemptible" if self._instance["preemptible"] else "non-preemptible"
        tokens["CT_RETRIES"] = str(self._instance["retries"])
        tokens["CT_JOB"] = self.node_name
        tokens["CT_SOURCE"] = self.source_path
        tokens["CT_TYPE"] = self.source_type

        for token in tokens:
            hou.putenv(token, tokens[token])

        tokens.update(parent_tokens)
        return tokens

    def get_args(self):
        """Prepare the args for submission to conductor.

        This dict represents the args that are specific to
        this job. It will be joined with the submission
        level args like notifications, and project, before
        submitting to Conductor.
        """
        result = {}

        result["upload_paths"] = self._resources["dependencies"]
        result["autoretry_policy"] = {'preempted': {
            'max_retries': self._instance["retries"]}
        } if self._instance["preemptible"] else {}
        result["software_package_ids"] = self._resources["package_ids"]
        result["preemptible"] = self._instance["preemptible"]
        result["environment"] = dict(
            self._resources["environment"])
        result["enforced_md5s"] = {}
        result["scout_frames"] = ", ".join([str(s) for s in
                                            self._sequence["scout"] or []])
        result["output_path"] = self._output_directory
        result["chunk_size"] = self._sequence["main"].chunk_size
        result["machine_type"] = self._instance["flavor"]
        result["cores"] = self._instance["cores"]
        result["tasks_data"] = [task.data() for task in self._tasks]
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
        return self._source["node"].path()

    @property
    def source_type(self):
        return self._source["type"]

    @property
    def dependencies(self):
        return self._resources["dependencies"]

    @property
    def package_ids(self):
        return self._resources["package_ids"]

    @property
    def environment(self):
        return self._resources["environment"]

    @property
    def tokens(self):
        return self._tokens

    @property
    def tasks(self):
        return self._tasks

    def _get_sequence(self):
        """Create the sequence object.

        In a simulation job, there is no need to duplicate
        the frame range section in the conductor::job node.
        Therefore it is hidden, and instead the frame range
        comes directly from the driver node. Scout frames
        will be None.
        """
        start, end, step = [
            self._source["node"].parm(parm).eval() for parm in [
                'f1', 'f2', 'f3']
        ]
        sequence = Sequence.create(start, end,  step)

        return {
            "main": sequence,
            "scout": None
        }


class ChunkedJob(Job):
    """ChunkedJob contains one task for each chunk of frames.

    It also contains a set of token variables relating to
    the chunking strategy.
    """

    def _get_sequence(self):
        """Create the sequence object from the job UI.

        As this is not a simulation job, the frames UI is
        visible and we use it. The Sequence contains chunk
        information, and we also get a sequence describing
        the scout frames.
        """
        return {
            "main": frame_spec_ui.main_frame_sequence(self._node),
            "scout": frame_spec_ui.resolved_scout_sequence(self._node)
        }

    def _setenv(self, parent_tokens):
        """Extra env tokens available to the user for a ChunkedJob.

        These tokens include information such as chunk_count
        and chunk_size in case the user wants to use them to
        construct strings.
        """
        tokens = {}
        seq = self._sequence["main"]
        sorted_frames = sorted(self._sequence["main"])
        tokens["CT_SCOUT"] = str(self._sequence["scout"])
        tokens["CT_CHUNKSIZE"] = str(self._sequence["main"].chunk_size)
        tokens["CT_CHUNKCOUNT"] = str(self._sequence["main"].chunk_count())
        tokens["CT_SCOUTCOUNT"] = str(len(self._sequence["scout"] or []))

        for token in tokens:
            hou.putenv(token, tokens[token])
        tokens.update(parent_tokens)

        super_tokens = super(ChunkedJob, self)._setenv(parent_tokens)
        tokens.update(super_tokens)
        return tokens
