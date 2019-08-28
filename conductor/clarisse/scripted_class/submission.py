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

Users can choose to localize contexts before submission (off by default) If they
turn it on then the flow is:
1. Make sure the user has saved the file. (they might need it)
5. Make contexts local.
6. Remove Conductor nodes.
7. Save the render package.
8. Do the submission.
9. Reload the saved file. This is slow for very big projects because of the time
   to reload the broject.

If they don't localize, then:
1. Save the render package.
2. Do the submission.


In this case the submission may contain xrefs nested to any level and we do a
pretty good job of resolving them. However, if the render errors due to xrfef
the localize method is the fallback.
"""

import datetime
import errno
import os
import shutil
import sys
import traceback

import conductor.clarisse.scripted_class.dependencies as deps
import conductor.clarisse.utils as cu
import ix
from conductor.clarisse.scripted_class import missing_files_ui
from conductor.clarisse.scripted_class.job import Job
from conductor.lib import conductor_submit
from conductor.native.lib.data_block import ConductorDataBlock
from conductor.native.lib.gpath import Path


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
    because in that case we get tto reload the scene after submission.
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
    bracket> tokens in order to build strings in the UI such as commands and job
    titles.
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
        self.should_delete_render_package = self.node.get_attribute(
            "clean_up_render_package"
        ).get_bool()

        self.local_upload = self.node.get_attribute("local_upload").get_bool()
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
                return Path("{}_ct{}.project".format(path, self.timestamp))
            else:
                return Path("{}_ct.project".format(path))
        except ValueError as err:
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
            list: list of response dictionariues, containing response codes
            and descriptions.
        """

        submission_args = self.get_args()
        self.write_render_package()

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
            if ex.errno == errno.EEXIST and os.path.isdir(tmpdir):
                pass
            else:
                raise

    def _copy_system_dependencies_to_temp(self):
        """
        Copy over all system dfependencies:

        Wrapper scripts, config files etc.
        """
        for entry in deps.system_dependencies():
            if os.path.isfile(entry["src"]):
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
