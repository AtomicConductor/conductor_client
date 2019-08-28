"""
Build an object to represent a Conductor job.
"""


import json
import os

import conductor.clarisse.scripted_class.dependencies as deps
import ix
from conductor.clarisse.scripted_class import frames_ui
from conductor.clarisse.scripted_class.task import Task
from conductor.native.lib.data_block import ConductorDataBlock
from conductor.native.lib.expander import Expander
from conductor.native.lib.gpath_list import PathList
from conductor.native.lib.sequence import Sequence


class Job(object):
    """
    Class Job holds all data for one Conductor Job in Clarisse.

    Jobs are owned by a Submission and a Job owns potentially many Tasks. Like a
    Submission, it also manages a list of tokens the user can access in thhe
    task template and other ConductorJob attributes.
    """

    def __init__(self, node, parent_tokens, render_package_path):
        """
        Build job object for a ConductorJob node.

        After _set_tokens has been called, the Job level token variables are
        valid and calls to evaluate string attributes will correctly resolve
        where those tokens have been used.  This is why we evaluate title,
        tasks, after the call to _set_tokens()

        Args:
            node (ConductorJob): item from which to build this job object
            parent_tokens (dict): token/value pairs in the scope of the
            submission (parent) object.
            render_package_path (string): The render project file, which must be
            added to this job's dependencies.
        """

        self.node = node
        self.tasks = []
        self.sequence = self._get_sequence()
        self.sources = self._get_sources()
        self.instance = self._get_instance()

        out = self._get_output_directory()
        self.common_output_path = out["common_path"]
        self.output_paths = out["output_paths"]

        tile_width = int(self.node.get_attribute("tiles").get_long())
        self.tiles = tile_width * tile_width

        self.tokens = self._set_tokens(parent_tokens)

        self.environment = self._get_environment()
        self.package_ids = self._get_package_ids()
        self.dependencies = deps.collect(self.node)

        try:
            self.dependencies.add(render_package_path)
        except ValueError as ex:
            ix.log_error("{} - while resolving {}".format(str(ex), render_package_path))

        expander = Expander(**self.tokens)
        self.title = expander.evaluate(self.node.get_attribute("title").get_string())

        # TODO: Add metadata UI
        self.metadata = None

        task_att = self.node.get_attribute("task_template")
        for chunk in self.sequence["main"].chunks():
            for tile_number in range(1, self.tiles + 1):
                tile_spec = (self.tiles, tile_number)
                self.tasks.append(
                    Task(chunk, task_att, self.sources, tile_spec, self.tokens)
                )

    def _get_sources(self):
        """
        Get the images/layers, along with associated Sequence objects.

        If we are not rendering a custom range, then the sequence for
        each image may be different.

        Returns:
            list of dict: elements contain an image along with the Sequence that
            represents the image range.
        """

        images = ix.api.OfObjectArray()
        self.node.get_attribute("images").get_values(images)

        use_custom = self.node.get_attribute("use_custom_frames").get_bool()

        # cast to list because OfObjectArray is true even when empty.
        if not list(images):
            ix.log_error("No render images. Please reference one or more image items")
        seq = self.sequence["main"]
        result = []
        for image in images:
            if not use_custom:
                seq = Sequence.create(*frames_ui.image_range(image))
            result.append({"image": image, "sequence": seq})
        return result

    def _get_extra_env_vars(self):
        """
        Collect any environment specified by the user.

        Returns:
            list of dict: name, value and merge policy of user specified env vars.
        """

        result = []
        json_entries = ix.api.CoreStringArray()
        self.node.get_attribute("extra_environment").get_values(json_entries)

        for entry in [json.loads(j) for j in json_entries]:
            result.append(
                {
                    "name": entry["key"],
                    "value": os.path.expandvars(entry["value"]),
                    "merge_policy": ["append", "exclusive"][int(entry["excl"])],
                }
            )

        return result

    def _get_environment(self):
        """
        Collect all environment variables.

        NOTE: Revisit and test the bespoke env added below in the amendments
        section.

        Returns:
            package_environment: Resolved package environment object.
        """

        package_tree = ConductorDataBlock(product="clarisse").package_tree()

        paths = ix.api.CoreStringArray()
        self.node.get_attribute("packages").get_values(paths)
        paths = list(paths)
        package_env = package_tree.get_environment(paths)

        extra_vars = self._get_extra_env_vars()
        package_env.extend(extra_vars)

        # Special Amendments!
        # Clearly we need to find a better value for PYTHONHOME and add it in
        # the sidecar
        amendments = [
            {
                "name": "PYTHONHOME",
                "value": "/opt/silhouettefx/silhouette/7/silhouette-7.5.2",
                "merge_policy": "exclusive",
            },
            {"name": "CONDUCTOR_PATHHELPER", "value": 0, "merge_policy": "exclusive"},
            {
                "name": "LD_LIBRARY_PATH",
                "value": "/usr/lib/python2.7/config-x86_64-linux-gnu",
                "merge_policy": "append",
            },
        ]
        package_env.extend(amendments)

        return package_env

    def _get_package_ids(self):
        """
        Package Ids for chosen packages.

        Returns:
            list: package ids as list of strings.
        """
        package_tree = ConductorDataBlock(product="clarisse").package_tree()
        paths = ix.api.CoreStringArray()
        self.node.get_attribute("packages").get_values(paths)
        results = []
        for path in paths:
            name = path.split("/")[-1]
            package = package_tree.find_by_name(name)
            if package:
                package_id = package.get("package_id")
                if package_id:
                    results.append(package_id)
        return results

    def _get_output_directory(self):
        """
        Get the common path for all image output paths.

        NOTE: We don't really need the subpaths any longer because directory
        creation is handled in the prerender script. Don't want to mess with
        things right now though.

        Returns:
            dict: common path and list of paths below it
        """
        out_paths = PathList()

        images = ix.api.OfObjectArray()
        self.node.get_attribute("images").get_values(images)

        for image in images:
            directory = os.path.dirname(image.get_attribute("save_as").get_string())
            try:
                out_paths.add(directory)
            except ValueError as ex:
                ix.log_error("{} - while resolving {}".format(str(ex), directory))
        return {"common_path": out_paths.common_path(), "output_paths": out_paths}

    def _get_instance(self):
        """
        Get everything related to the instance.

        Get the machine type, preemptible flag, and number of retries if
        preemptible. We use the key from the instance_type menu and look
        up the machine spec in the shared data where the full list of
        instance_types is stored. When exhaustion API is in effect, the
        list of available types may be dynamic, so wetell the user to
        refresh.

        Returns:
            dict: Fields to specify the render node behaviour.
        """

        instance_types = ConductorDataBlock(product="clarisse").instance_types()
        label = self.node.get_attribute("instance_type").get_applied_preset_label()

        result = {
            "preemptible": self.node.get_attribute("preemptible").get_bool(),
            "retries": self.node.get_attribute("retries").get_long(),
        }

        try:
            found = next(it for it in instance_types if str(it["description"]) == label)
        except StopIteration:
            ix.log_error(
                'Invalid instance type "{}". Try a refresh (connect).'.format(label)
            )

        result.update(found)
        return result

    def _get_sequence(self):

        """
        Get sequence objects from the frames section of the UI.

        Returns:
            dict: main sequence and scout sequence.
        """
        return {
            "main": frames_ui.main_frame_sequence(self.node),
            "scout": frames_ui.resolved_scout_sequence(self.node),
        }

    def _set_tokens(self, parent_tokens):
        """
        Constructs angle bracket tokens dictionary.

        Collect token values for this Job and merge with those from the
        parent Submission.

        Args:
            parent_tokens (dict): tokens that were resolved in the parent
            (submission) object.

        Returns:
            dict: combined dictionary of tokens in scope for this job.
        """
        tokens = {}
        main_seq = self.sequence["main"]
        scout_seq = self.sequence["scout"]

        tokens["ct_scout"] = str(scout_seq)
        tokens["ct_chunksize"] = str(main_seq.chunk_size)
        tokens["ct_chunkcount"] = str(main_seq.chunk_count())
        tokens["ct_scoutcount"] = str(len(scout_seq or []))
        tokens["ct_sequencelength"] = str(len(main_seq))
        tokens["ct_sequence"] = str(main_seq)
        tokens["ct_sequencemin"] = str(main_seq.start)
        tokens["ct_sequencemax"] = str(main_seq.end)
        tokens["ct_instance_type"] = self.instance["name"]
        tokens["ct_instance"] = self.instance["description"]
        tokens["ct_tiles"] = str(self.tiles)
        pidx = int(self.instance["preemptible"])
        tokens["ct_preemptible"] = "preemptible" if pidx else "non-preemptible"
        tokens["ct_retries"] = str(self.instance["retries"])
        tokens["ct_job"] = self.node_name

        # Space delimited list of output paths are needed for a mkdir cmd. As
        # mentioned above, no longer needed now that directories are created in
        # the prerender script. Just don't want to remove right now as no time
        # to test.
        tokens["ct_directories"] = " ".join(
            '"{}"'.format(p.posix_path(with_drive=False)) for p in self.output_paths
        )

        tokens.update(parent_tokens)
        return tokens

    def get_args(self, upload_only):
        """
        Prepare the args for submission to conductor.

        Args:
            upload_only (bool): Don't construct tasks in an upload only job.

        Returns:
            dict: This dict represents the args that are specific to this job.
            It will be joined with the submission level args like notifications,
            and project, before submitting to Conductor.
        """
        result = {}
        result["upload_paths"] = sorted([d.posix_path() for d in self.dependencies])
        result["autoretry_policy"] = (
            {"preempted": {"max_retries": self.instance["retries"]}}
            if self.instance["preemptible"]
            else {}
        )
        result["software_package_ids"] = self.package_ids
        result["preemptible"] = self.instance["preemptible"]
        result["environment"] = dict(self.environment)
        result["enforced_md5s"] = {}
        result["scout_frames"] = ", ".join(
            [str(s) for s in self.sequence["scout"] or []]
        )
        result["output_path"] = self.common_output_path.posix_path()
        result["chunk_size"] = self.sequence["main"].chunk_size
        result["instance_type"] = self.instance["name"]
        if not upload_only:
            result["tasks_data"] = [task.data() for task in self.tasks]

        result["job_title"] = self.title
        if self.metadata:
            result["metadata"] = self.metadata
        result["priority"] = 5
        result["max_instances"] = 0
        return result

    @property
    def node_name(self):
        return self.node.get_name()
