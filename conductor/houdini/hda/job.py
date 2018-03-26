"""Build an object to represent a Conductor job.

Attributes:     OUTPUT_DIR_PARMS (dict): If the user has chosen to
derive the output directory automatically from the driver node, we need
to know the name of the parm that contains the output path, which is
different for each kind of node.
"""

import os

import hou
import json
from conductor.houdini.lib import data_block
from conductor.houdini.lib.sequence.clump import Clump
from conductor.houdini.lib.sequence.sequence import Sequence


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
    """class Job holds all data for one Conductor job.

    A Job is contained by a Submission and contains
    potentially many Tasks. Like a Submission, it also
    manages a list of environment tokens that the user can
    access as $ variables. There are two Job subclasses,
    ClumpedJob and SingleTaskJob. A clumped job makes use of
    the frame range specification in the UI to calculate how
    to manufacture a Task for each Clump. A SingleTaskJob is
    useful for simulations or other processes where it
    doesn't make sense to split the job into time based
    clumps. A factory method is used to figure out if the
    job should be a ClumpedJob or a Simulation.
    """
    @staticmethod
    def create(node, tokens, scene):
        """Factory makes one of the Job subclasses.

        ClumpedJob makes a task per clump. SingleTaskJob
        makes one task representing the whole time range.
        """
        print "CREATE !!!!!!!"
        print node
        if driver_ui.is_simulation(node):
            return SingleTaskJob(node, tokens, scene)
        return ClumpedJob(node, tokens, scene)

    def __init__(self, node, parent_tokens, scene_file):
        """Build the common jpb member data in this base class.

        * Get the driver node and type.
        * Get the instance type, retries, and preemptible flag.
        * Get the sequence.
        * Fetch dependencies, append scene file (which may not exist).
        * Get the Conductor package IDs and environment.
        * Get the task command, which will be expanded later per-clump

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
        self._source_node = driver_ui.get_driver_node(self._node)
        self._source_type = driver_ui.get_driver_type(self._node)
        self._get_instance()
        self._get_sequence()
        self._dependencies = dependency_scan.fetch(self._sequence)
        self._dependencies.append(scene_file)
        self._package_ids = software_ui.get_chosen_ids(self._node)
        self._environment = software_ui.get_environment(self._node)
        self._task_command = self._node.parm("task_command").unexpandedString()

        self._tokens = self._setenv(parent_tokens)

        self._title = self._node.parm("job_title").eval()
        self._output_directory = self._get_output_dir()
        self._metadata = self._node.parm("metadata").eval()

        self._tasks = []
        for clump in self._sequence.clumps():
            task = Task(clump, self._task_command, self._tokens)
            self._tasks.append(task)

    def _get_output_dir(self):
        """Get the directory that will be made available for download.

        By default, try to derive the output directory from
        the output path in the driver node. We do this by
        looking up the parm name based on the driver node
        type in OUTPUT_DIR_PARMS. If its not a node we know
        about (or even if it is), the user can select to
        override and specify a directory manually. If in
        either case, no directory is specified we fall back
        to $JOB/render.
        """
        result = os.path.join(hou.getenv("JOB"), "render")
        if self._node.parm('override_output_dir').eval():
            ov_dir = self._node.parm('output_directory').eval()
            if ov_dir:
                result = ov_dir
        else:
            parm_name = OUTPUT_DIR_PARMS.get(self._source_type)
            if parm_name:
                path = self._source_node.parm(parm_name).eval()
                ov_dir = os.path.dirname(path)
                if ov_dir:
                    result = ov_dir
        return result

    def _get_instance(self):
        """Get everything related to the instance.

        Get up the machine type, preemptible flag, and
        number of retries if preemptible.
        """
        flavor, cores = self._node.parm(
            'machine_type').eval().split("_")

        instance_types = data_block.ConductorDataBlock(
            product="houdini").instance_types()

        result = [it for it in instance_types if it['cores'] ==
                  int(cores) and it['flavor'] == flavor][0]
        result["preemptible"] = bool(self._node.parm('preemptible').eval())
        result["retries"] = self._node.parm("retries").eval()
        self._instance = result

    def get_args(self):
        """Prepare the args for submission to conductor.

        This dict represents the args that are specific to
        this job. It will be joined with the submission
        level args like notifications, and project, before
        submitting to Conductor.
        """
        result = {}

        result["upload_paths"] = self._dependencies
        result["autoretry_policy"] = {'preempted': {
            'max_retries': self._instance["retries"]}
        } if self._instance["preemptible"] else {}
        result["software_package_ids"] = self._package_ids
        result["preemptible"] = self._instance["preemptible"]
        result["environment"] = dict(self._environment)
        result["enforced_md5s"] = {}
        result["scout_frames"] = ", ".join(self._scout_sequence or [])
        result["output_path"] = self._output_directory
        result["chunk_size"] = self._sequence.clump_size
        result["machine_type"] = self._instance.get("flavor")
        result["cores"] = self._instance.get("cores")
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

    def _get_sequence(self):
        """Create a sequence object to define time range.

        Among other things, a jobs time range is used to
        make sure dependencies are only gathered for frames
        where they are used. This method must be overridden
        in derived classes.
        """
        raise NotImplementedError()

    def _setenv(self, parent_tokens):
        """Set up job level env tokens.

        The list of available tokens is different for
        derived classes and this method must therefore be
        overridden.
        """
        raise NotImplementedError()


class ClumpedJob(Job):
    """ClumpedJob contains one task for each clump of frames.

    It also contains a set of token variables, accessible to
    the user, relating to the clumping strategy.
    """

    def __init__(self, node, parent_tokens, scene_file):
        """Init using the base class.

        The base class __init__ will call the overridden
        methods defined below.
        """
        super(ClumpedJob, self).__init__(node, parent_tokens, scene_file)

    def _get_sequence(self):
        """Create the sequence object from the job UI.

        As this is not a simulation job, the frames UI is
        visible and we use it. The Sequence contains clump
        information, and we also get a sequence describing
        the scout frames.
        """
        self._sequence = frame_spec_ui.main_frame_sequence(self._node)
        self._scout_sequence = frame_spec_ui.resolved_scout_sequence(
            self._node)

    def _setenv(self, parent_tokens):
        """Env tokens available to the user for a ClumpedJob.

        These tokens include information such as clump_count
        and clump_size in case the user wants to use them to
        construct strings.
        """
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


class SingleTaskJob(Job):
    """SingleTaskJob contains one task for the job.

    It also contains a set of token variables, accessible to
    the user that are appropriate for a single task job.
    """

    def __init__(self, node, parent_tokens, scene_file):
        """Init using the base class.

        The base class __init__ will call the overridden
        methods defined below.
        """
        super(SingleTaskJob, self).__init__(node, parent_tokens, scene_file)

    def _get_sequence(self):
        """Create the sequence object.

        In a simulation job, there is no need to duplicate
        the frame range section in the conductor::job node.
        Therefore it is hidden, and instead the frame range
        comes directly from the driver node. To make sure we
        only get one task, set clumpsize to the length of
        the sequence. And of course scout frames will be
        None.
        """
        start, end, step = [
            self._source_node.parm(parm).eval() for parm in [
                'f1', 'f2', 'f3']
        ]
        self._sequence = Sequence.from_range(start, end, step=step)
        self._sequence.clump_size = len(self._sequence)
        self._scout_sequence = None

    def _setenv(self, parent_tokens):
        """Env tokens for a SingleTaskJob.

        There is effectively one clump and therefore it
        makes no sense to provide tokens related to clump
        size or clump count.
        """
        tokens = {}
        sorted_frames = sorted(self._sequence._frames)
        tokens["CT_LENGTH"] = str(len(self._sequence))
        tokens["CT_SEQUENCE"] = str(Clump.create(iter(self._sequence)))
        tokens["CT_SEQUENCEMIN"] = str(sorted_frames[0])
        tokens["CT_SEQUENCEMAX"] = str(sorted_frames[-1])
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
