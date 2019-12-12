"""
Build an object to represent a Clarisse Conductor submission.

Also handle the submit action.

NOTE There are some bugs in clarisse that have lead to some decisions for the
submission flow.

1. Bug where some nested path overrides don't correctly get overridden when
   opening the project.

2. Undo doesn't work on deeply nested reference contexts. If you make-all-local
   in a batch undo block, then when you undo, there are extra nodes in the
   project.

Users can choose to localize contexts before submission (off by default).
If they turn it on then the flow is:
*. Make sure the user has saved the file. (they might need it)
*. Make contexts local.
*. Remove Conductor nodes.
*. Save the render package.
*. Do the submission.
*. Reload the saved file. This is slow for very big projects because of the time
   to reload the project.

If they don't localize, then:
*. Save the render package.
*. Do the submission.

In this case the submission may contain xrefs nested to any level and we do a
pretty good job of resolving them. However, if the render errors due to xref
the localize method is the fallback.
"""

import datetime
import errno
import fileinput
import os
import re
import shutil
import sys
import tempfile
import traceback

import conductor.clarisse.clarisse_config as ccfg
import conductor.clarisse.scripted_class.dependencies as deps
import conductor.clarisse.utils as cu
import ix
from conductor.clarisse.scripted_class import missing_files_ui
from conductor.clarisse.scripted_class.job import Job
from conductor.lib import conductor_submit
from conductor.native.lib.data_block import ConductorDataBlock
from conductor.native.lib.gpath import Path
from conductor.native.lib.gpath_list import PathList

PROJECT_EXTENSION_REGEX = r"(\.ct\.project|\.project)"
CT_PROJECT_EXTENSION = ".ct.project"


def _get_path_line_regex():
    """
    Generate a regex to help identify filepath attributes.

    As we scan project files to replace windows paths, we use this regex which
    will be something like: r'\s+(?:filename|filename_sys|save_as)\s+"(.*)"\s+' 
    only longer.
    """
    classes = ix.application.get_factory().get_classes()
    file_attrs = []
    for klass in classes.get_classes():
        attr_count = klass.get_attribute_count()
        for i in range(attr_count):
            attr = klass.get_attribute(i)
            hint = attr.get_visual_hint()
            if hint in [
                ix.api.OfAttr.VISUAL_HINT_FILENAME_SAVE,
                ix.api.OfAttr.VISUAL_HINT_FILENAME_OPEN,
                ix.api.OfAttr.VISUAL_HINT_FOLDER,
            ]:
                file_attrs.append(attr.get_name())

    file_attrs = list(set(file_attrs))
    file_attrs.sort()
    return r"\s+(?:" + "|".join(file_attrs) + r')\s+"(.*)"\s+'


def _localize_contexts():
    """
    Make all clarisse reference contexts local.

    This is the equivalent of importing Maya references and is optional for the
    user.
    """
    contexts = ix.api.OfContextSet()
    ix.application.get_factory().get_root().resolve_all_contexts(contexts)
    for ctx in contexts:
        if ctx.is_reference() and ctx.get_attribute("filename").get_string().endswith(
            ".project"
        ):
            ix.cmds.MakeLocalContext(ctx)


def _remove_conductor():
    """
    Remove all Conductor data from the render archive.

    This ensures the render logs are not polluted by complaints about Conductor
    nodes. This can only be done in the situation where we localize contexts,
    because in that case we get to reload the scene after submission.
    """
    objects = ix.api.OfObjectArray()
    ix.application.get_factory().get_objects("ConductorJob", objects)
    for item in list(objects):
        ix.application.get_factory().remove_item(item.get_full_name())


class Submission(object):
    """
    Submission holds all data needed for a submission.

    It has potentially many Jobs, and those Jobs each have many Tasks. A
    Submission can provide the correct args to send to Conductor, or it can be
    used to create a dry run to show the user what will happen.

    A Submission also sets a list of tokens that the user can access as <angle
    bracket> tokens in order to build strings in the UI such as commands, job
    title, and (soon to be added) metadata.
    """

    def __init__(self, obj):
        """
        Collect data from the Clarisse UI.

        Collect attribute values that are common to all jobs, then call
        _set_tokens(). After _set_tokens has been called, the Submission level
        token variables are valid and calls to evaluate expressions will
        correctly resolve where those tokens have been used.
        """
        self.node = obj

        if self.node.is_kindof("ConductorJob"):
            self.nodes = [obj]
        else:
            raise NotImplementedError

        self.localize_before_ship = self.node.get_attribute(
            "localize_contexts"
        ).get_bool()
        self.project_filename = ix.application.get_current_project_filename()
        self.timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        self.timestamp_render_package = self.node.get_attribute(
            "timestamp_render_package"
        ).get_bool()

        self.tmpdir = Path(
            os.path.join(
                ix.application.get_factory().get_vars().get("CTEMP").get_string(),
                "conductor",
            )
        )
        self.render_package_path = self._get_render_package_path()
        self.local_upload = self.node.get_attribute("local_upload").get_bool()

        self.should_delete_render_package = (
            self.node.get_attribute("clean_up_render_package").get_bool()
            and self.local_upload
        )

        self.force_upload = self.node.get_attribute("force_upload").get_bool()
        self.upload_only = self.node.get_attribute("upload_only").get_bool()
        self.project = self._get_project()
        self.notifications = self._get_notifications()
        self.tokens = self._set_tokens()

        self.jobs = []
        for node in self.nodes:
            job = Job(node, self.tokens, self.render_package_path)
            self.jobs.append(job)

    def _get_project(self):
        """Get the project from the attr.

        Get its ID in case the current project is no longer in the list
        of projects at conductor, throw an error.
        """

        projects = ConductorDataBlock().projects()
        project_att = self.node.get_attribute("conductor_project_name")
        label = project_att.get_applied_preset_label()
        try:
            found = next(p for p in projects if str(p["name"]) == label)
        except StopIteration:
            ix.log_error('Cannot find project "{}" at Conductor.'.format(label))

        return {"id": found["id"], "name": str(found["name"])}

    def _get_notifications(self):
        """Get notification prefs."""
        if not self.node.get_attribute("notify").get_bool():
            return None

        emails = self.node.get_attribute("email_addresses").get_string()
        return [email.strip() for email in emails.split(",") if email.strip()]

    def _set_tokens(self):
        """Env tokens are variables to help the user build expressions.

        The user interface has fields for strings such as job title,
        task command. The user can use these tokens with <angle brackets> to build those strings. Tokens at the Submission
        level are also available in Job level fields, and likewise
        tokens at the Job level are available in Task level fields.
        """
        tokens = {}

        pdir_val = ix.application.get_factory().get_vars().get("PDIR").get_string()

        tokens["ct_pdir"] = '"{}"'.format(Path(pdir_val).posix_path(with_drive=False))

        tokens["ct_temp_dir"] = "{}".format(self.tmpdir.posix_path(with_drive=False))
        tokens["ct_timestamp"] = self.timestamp
        tokens["ct_submitter"] = self.node.get_name()

        tokens["ct_render_package"] = '"{}"'.format(
            self.render_package_path.posix_path(with_drive=False)
        )

        tokens["ct_project"] = self.project["name"]

        return tokens

    def _get_render_package_path(self):
        """
        Calc the path to the render package.

        The name is not always known until
        preview/submission time because it is based on the filename and
        possibly a timestamp. What this means, practically, is that it won't
        show up in the extra uploads window along with
        other dependencies when the glob or smart-scan button is pushed.
        It will however always show up in the preview window.

        We replace spaces in the filename because of a bug in Clarisse
        https://www.isotropix.com/user/bugtracker/376

        Returns:
            string: path
        """
        current_filename = ix.application.get_current_project_filename()
        path = os.path.splitext(current_filename)[0]

        path = os.path.join(
            os.path.dirname(path), os.path.basename(path).replace(" ", "_")
        )

        try:
            if self.timestamp_render_package:
                return Path("{}_{}.ct.project".format(path, self.timestamp))
            else:
                return Path("{}.ct.project".format(path))
        except ValueError:
            ix.log_error(
                'Cannot create a submission from this file: "{}". Has it ever been saved?'.format(
                    current_filename
                )
            )

    def get_args(self):
        """
        Prepare the args for submission to conductor.

        Returns:
            list: list of dicts containing submission args per job.
        """

        result = []
        submission_args = {}

        submission_args["local_upload"] = self.local_upload
        submission_args["upload_only"] = self.upload_only
        submission_args["force"] = self.force_upload
        submission_args["project"] = self.project["name"]
        submission_args["notify"] = self.notifications

        for job in self.jobs:
            args = job.get_args(self.upload_only)
            args.update(submission_args)
            result.append(args)
        return result

    def submit(self):
        """
        Submit all jobs.

        Returns:
            list: list of response dictionaries, containing response codes
            and descriptions.
        """

        submission_args = self.get_args()
        self._before_submit()

        do_submission, submission_args = self.legalize_upload_paths(submission_args)
        results = []
        if do_submission:

            for job_args in submission_args:
                try:
                    remote_job = conductor_submit.Submit(job_args)
                    response, response_code = remote_job.main()
                    results.append({"code": response_code, "response": response})
                except BaseException:
                    results.append(
                        {
                            "code": "undefined",
                            "response": "".join(
                                traceback.format_exception(*sys.exc_info())
                            ),
                        }
                    )
            for result in results:
                ix.log_info(result)
        else:
            return [{"code": "undefined", "response": "Submission cancelled by user"}]

        self._after_submit()
        return results

    def _before_submit(self):
        """
        Prepare the project files that will be shipped.

        We first write out the current project file. 
        
        Then (on Windows) we find additional referenced project 
        files and adjust paths in all of them so they may be 
        rendered on linux render nodes.
        """
        self.write_render_package()
        if cu.is_windows():
            self._linuxify_project_references()
            self._linuxify_render_package()

    def write_render_package(self):
        """
        Write a package suitable for rendering.

        A render package is a project file with a special name.
        """

        app = ix.application
        clarisse_window = app.get_event_window()

        self._before_write_package()
        current_filename = app.get_current_project_filename()
        current_window_title = clarisse_window.get_title()

        package_file = self.render_package_path.posix_path()
        with cu.disabled_app():
            success = ix.application.save_project(package_file)
            ix.application.set_current_project_filename(current_filename)
            clarisse_window.set_title(current_window_title)

        self._after_write_package()

        if not success:
            ix.log_error("Failed to export render package {}".format(package_file))

        ix.log_info("Wrote package to {}".format(package_file))
        return package_file

    def _linuxify_project_references(self):
        """
        Make copies of project files on Windows that are suitable for linux.

        Copies have the special conductor extension: ".ct.project".
        We convert all paths to posix. We also adjust references to
        other projects to point to the ".ct.project" version, because the 
        .ct.project version will also be linuxified.

        """
        ix.log_info("Adjust project references for Linux")
        paths = PathList()

        contexts = ix.api.OfContextSet()
        ix.application.get_factory().get_root().resolve_all_contexts(contexts)
        for context in contexts:
            if context.is_reference() and not context.is_disabled():
                try:
                    filename = context.get_attribute("filename").get_string()
                    if filename.endswith(".project"):
                        paths.add(filename)
                except ValueError as ex:
                    ix.log_error(
                        "{} - while resolving reference {}.filename = {}".format(
                            str(ex), str(context), filename
                        )
                    )

        # Now we have a list of all filenames that need to be adjusted.
        # So we rewrite each file, and any references to other files they may contain.
        PATH_LINE_REGEX = _get_path_line_regex()
        for path in paths:
            ix.log_info("Adjust paths in {}".format(path.posix_path()))
            self._linuxify_file(path.posix_path(), PATH_LINE_REGEX)

    def _linuxify_render_package(self):
        """
        Adjust reference pasths for windows.
        """
        PATH_LINE_REGEX = _get_path_line_regex()
        temp_path = os.path.join(
            tempfile.gettempdir(), next(tempfile._get_candidate_names())
        )
        shutil.copy2(self.render_package_path.posix_path(), temp_path)

        os.remove(self.render_package_path.posix_path())
        self._linuxify_file(
            temp_path, PATH_LINE_REGEX, self.render_package_path.posix_path()
        )

    def _linuxify_file(self, filename, path_regex, dest_path=None):
        """
        Fix paths for one file.

        If the file already has the .ct.project extension, replace it too,
        """
        out_filename = dest_path
        if not dest_path:
            out_filename = re.sub(
                PROJECT_EXTENSION_REGEX, CT_PROJECT_EXTENSION, filename
            )

        with open(out_filename, "w+") as outfile:
            with open(filename, "r+") as infile:
                for line in infile:
                    outfile.write(self._replace_path(line, path_regex))

    def _replace_path(self, line, path_regex):
        """
        Detect paths in the line of text and make a replacement.

        Args:
            line (string): line from the file.

        Returns:
            string: The line, possibly with replaced path
        """

        match = re.match(path_regex, line)
        if match:
            path = Path(match.group(1), no_expand=True).posix_path(with_drive=False)
            path = re.sub(PROJECT_EXTENSION_REGEX, CT_PROJECT_EXTENSION, path)
            return line.replace(match.group(1), path)

        return line

    def legalize_upload_paths(self, submission_args):
        """
        Alert the user of missing files. If the user doesn't want to continue
        with missing files, the result will be False. Otherwise it will be True
        and the potentially adjusted args are returned.

        Args:
            submission_args (list): list of job args.

        Returns:
           tuple (bool, adjusted args):
        """
        missing_files = []

        for job_args in submission_args:
            existing_files = []
            for path in job_args["upload_paths"]:
                if os.path.exists(path):
                    existing_files.append(path)
                else:
                    missing_files.append(path)

            job_args["upload_paths"] = existing_files
        missing_files = sorted(list(set(missing_files)))
        if not missing_files_ui.proceed(missing_files):
            return (False, [])
        return (True, submission_args)

    def _before_write_package(self):
        """
        Prepare to write render package.
        """
        if self.localize_before_ship:
            _localize_contexts()
            _remove_conductor()

        self._prepare_temp_directory()
        self._copy_system_dependencies_to_temp()

    def _prepare_temp_directory(self):
        """
        Make sure the temp directory has a conductor subdirectory.
        """
        tmpdir = self.tmpdir.posix_path()
        try:
            os.makedirs(tmpdir)
        except OSError as ex:
            if not (ex.errno == errno.EEXIST and os.path.isdir(tmpdir)):
                raise

    def _copy_system_dependencies_to_temp(self):
        """
        Copy over all system dependencies to a tmp folder.

        Wrapper scripts, config files etc. The clarisse.cfg file is special. See
        ../clarisse_config.py
        """
        for entry in deps.system_dependencies():
            if os.path.isfile(entry["src"]):
                if entry["src"].endswith(".cfg"):
                    safe_config = ccfg.legalize(entry["src"])
                    with open(entry["dest"], "w") as dest:
                        dest.write(safe_config)
                    ix.log_info(
                        "Copy with mods {} to {}".format(entry["src"], entry["dest"])
                    )
                else:
                    ix.log_info("Copy {} to {}".format(entry["src"], entry["dest"]))
                    shutil.copy(entry["src"], entry["dest"])

    def _after_submit(self):
        """Clean up, and potentially other post submission actions."""
        self._delete_render_package()

    def _after_write_package(self):
        """
        Runs operations after saving the render package.

        If we did something destructive, like localize contexts, then
        a backup will have been saved and we now reload it. This strategy
        is used because Clarisse's undo is broken when it comes to
        undoing context localization.
        """
        if self.localize_before_ship:
            self._revert_to_saved_scene()

    def _delete_render_package(self):
        """
        Delete the render package from disk if the user wants to.
        """
        if self.should_delete_render_package:
            render_package_file = self.render_package_path.posix_path()
            if os.path.exists(render_package_file):
                os.remove(render_package_file)

    def _revert_to_saved_scene(self):
        """
        If contexts were localized, we will load the saved scene.
        """
        with cu.waiting_cursor():
            with cu.disabled_app():
                ix.application.load_project(self.project_filename)

    @property
    def node_name(self):
        """node_name."""
        return self.node.get_name()

    @property
    def filename(self):
        """filename."""
        return ix.application.get_current_project_filename()

    def has_notifications(self):
        """has_notifications."""
        return bool(self.notifications)

    @property
    def email_addresses(self):
        """email_addresses."""
        if not self.has_notifications():
            return []
        return self.notifications["email"]["addresses"]
