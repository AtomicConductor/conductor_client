"""Build an object to represent a Clarisse Conductor submission.

Also handle the submit action.

NOTE There are a number of bugs in clarisse that have lead to the
decision for a particular submission flow. See submit() and
write_render_package() . The flow is:
1. Make sure the user has saved the file. (they might need it)
2. Prepare the temp directory.
3. Copy Conductor strip_drive_letter script to temp.
4. Make sure image ranges are valid.
5. Make contexts local.
6. Remove Conductor nodes.
7. Save the render package.
8. Do the submission.
9. Clean up temp files.

The bugs and reasonong that lead to this are:
1. BUG: Images don't render if their on-node frame range does not
contain the frames specified in the render command. The cli frames
should take precedence, but as they don't, we have to pre adjust
them. Undo doesn't work correctly for the relevant attributes, so
after adjustment they must be returned to their original values.
2.BUG:  Undo doesn't work on deeply nested reference contexts. If
you`make-all-local` in a batch undo block, then when you undo,
there are extra nodes in the project.

We export a render package as opposed to a regular project because
all paths containing variables are resolved.

We make-all-local (import referenced files) before exporting for
many reasons -

A. Bug where  some nested path overrides don't correctly get
overridden when opening the project. (I have to manually set
one every time I open the project). The same bug would appear
on the remote machine if we don't make refs local.
B. During development, a strategy was tried where drive letter
removal was run recursively on contexts on the remote machine
and it crashed with obscure errors. The same script succeeded
in the local interactive session, so I abandoned that path.
C. Isotropix plan to have refs made local for render packages
anyway. It's just not implemented yet.

So the combination of undo bugs and the need to make changes
to the scene before export, is why we:
(save, change, export, revert)
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
from conductor.clarisse.scripted_class import frames_ui
from conductor.clarisse.scripted_class import missing_files_ui
from conductor.clarisse.scripted_class.job import Job
from conductor.lib import conductor_submit
from conductor.native.lib.data_block import ConductorDataBlock
from conductor.native.lib.gpath import Path, GPathError
from conductor.native.lib.gpath_list import PathList

SCRIPTS_DIRECTORY = os.path.join(
    os.environ["CONDUCTOR_LOCATION"], "conductor", "clarisse", "scripts"
)


def _localize_contexts():
    """Make all clarisse reference contexts local.

    This is the equivalent of importing Maya references. We do this
    because on Windows it can be a bit fragile to have a scene
    containing nested project references that need drive letters
    resolved before they can find deeper referenced paths. Clarisse
    project files are generally small because they get everything heavy
    from geometry caches, so making refs local is very unlikely to have
    an effect on upload size. Having said that, We can try to omit this
    (and include project refs in the dep scan) once the tool is proven
    stable.
    """
    contexts = ix.api.OfContextSet()
    ix.application.get_factory().get_root().resolve_all_contexts(contexts)
    for ctx in contexts:
        if ctx.is_reference() and ctx.get_attribute("filename").get_string().endswith(
            ".project"
        ):
            ix.cmds.MakeLocalContext(ctx)


def _remove_conductor():
    """Remove all Conductor data from the render archive.

    This ensures the render logs are not polluted by complaints about
    Conductor nodes.
    """
    objects = ix.api.OfObjectArray()
    ix.application.get_factory().get_objects("ConductorJob", objects)
    for item in list(objects):
        ix.application.get_factory().remove_item(item.get_full_name())


class Submission(object):
    """class Submission holds all data needed for a submission.

    A Submission has potentially many Jobs, and those Jobs each have
    many Tasks. A Submission can provide the correct args to send to
    Conductor, or it can be used to create a dry run to show the user
    what will happen. A Submission also sets a list of tokens that the
    user can access as Clarisse custom variables in order to build
    strings in the UI such as commands and job titles.
    """

    def __init__(self, obj):
        """Collect data from the Clarisse UI.

        Collect attribute values that are common to all jobs, then call
        setenv(). After _set_tokens has been called, the Submission level
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

        self.tmpdir = Path(deps.CONDUCTOR_TMP_DIR)
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
        task command. The user can use these env tokens in SeExpr
        expressions to build those strings. Tokens at the Submission
        level are also available in Job level fields, and likewise
        tokens at the Job level are available in Task level fields.
        However, it makes no sense the other way, for example you can't
        use a chunk token (available at Task level) in a Job title
        expression because a chunk changes for every task. Once tokens
        are set, strings using them are expanded correctly. In fact we
        don't need these tokens to be stored as member data on the
        Submission object (or Job or Task) for the submission to
        succeed. The only reason we store them is to display them in a
        dry-run scenario.
        """
        tokens = {}

        pdirval = ix.application.get_factory().get_vars().get("PDIR").get_string()

        tokens["ct_pdir"] = '"{}"'.format(Path(pdirval).posix_path(with_drive=False))

        tokens["ct_temp_dir"] = "{}".format(self.tmpdir.posix_path(with_drive=False))
        tokens["ct_timestamp"] = self.timestamp
        tokens["ct_submitter"] = self.node.get_name()

        tokens["ct_render_package"] = '"{}"'.format(
            self.render_package_path.posix_path(with_drive=False)
        )

        tokens["ct_project"] = self.project["name"]

        return tokens

    def _get_render_package_path(self):
        """Calc the path to the render package.

        This is the only upload path that is not provided by
        dependencies.py, as the name is not always known until
        preview/submission time because it is based on the filename and
        possibly a timestamp. What this means, practically, is that it won't 
        show up in the extra uploads window along with 
        other dependencies when the glob or smart-scan button is pushed. 
        It will however always show up in the preview window.

        We replace spaces in the filename because of a bug in Clarisse
        https://www.isotropix.com/user/bugtracker/376
        Also see related `cd` in `DEFAULT_CMD_TEMPLATE` conductor_job.py
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
        except GPathError as err:
            ix.log_error(
                'Cannot create a submission from this file: "{}". Has it ever been saved?'.format(
                    current_filename
                )
            )

    def get_args(self):
        """Prepare the args for submission to conductor.

        This is a list where there is one args object for each Conductor
        job. The project, notifications, and upload args are the same
        for all jobs, so they are set here. Other args are provided by
        Job objects and updated with these submission level args to form
        each complete submission.
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
        """Submit all jobs.

        Collect responses and show them in the log.
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

    # def _before_submit(self):
    #     """"""
    #     self.write_render_package()
    #     self.validate_upload_paths()

    def write_render_package(self):
        """Write a package suitable for rendering.

        A render package is a binary package designed for rendering. It
        has the same name as the project, but with .render for the
        extension. It is a binary, around half the size of a project
        file. Before saving, all reference contexts are made local, and
        all Conductor data is removed.

        It is saved in the clarisse temp folder CTEMP.
        """

        app = ix.application
        self._before_write_package()
        current_filename = app.get_current_project_filename()

        package_file = self.render_package_path.posix_path()
        with cu.disabled_app():
            success = ix.application.save_project(package_file)
            ix.application.set_current_project_filename(current_filename)

        if os.environ.get("CONDUCTOR_SAVE_SNAPSHOTS"):
            filename = os.path.join(
                os.path.dirname(app.get_current_project_filename()), "ct_debug.project"
            )
            with cu.disabled_app():
                app.save_project_snapshot(filename)

        self._after_write_package()

        if not success:
            ix.log_error("Failed to export render package {}".format(package_file))

        ix.log_info("Wrote package to {}".format(package_file))
        return package_file

    def legalize_upload_paths(self, submission_args):
        missing_files = []

        for job_args in submission_args:
            existing_files = []
            for path in job_args["upload_paths"]:
                existing_files.append(path) if os.path.exists(
                    path
                ) else missing_files.append(path)
            job_args["upload_paths"] = existing_files
        if not missing_files_ui.proceed(missing_files):
            return (False, [])
        return (True, submission_args)

    def _before_write_package(self):
        """Prepare to write render package."""
        if self.localize_before_ship:
            _localize_contexts()
            _remove_conductor()

        self._prepare_temp_directory()
        self._copy_scripts_to_temp()

    def _prepare_temp_directory(self):
        """Make sure the temp directory has a conductor subdirectory.
        """
        tmpdir = self.tmpdir.posix_path()
        try:
            os.makedirs(tmpdir)
        except OSError as ex:
            if ex.errno == errno.EEXIST and os.path.isdir(tmpdir):
                pass
            else:
                raise

    def _copy_scripts_to_temp(self):
        for script in deps.CONDUCTOR_SCRIPTS:
            script_path = os.path.join(SCRIPTS_DIRECTORY, script)
            if os.path.isfile(script_path):
                shutil.copy(script_path, self.tmpdir.posix_path())

    def _after_submit(self):
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
        if self.should_delete_render_package:
            render_package_file = self.render_package_path.posix_path()
            if os.path.exists(render_package_file):
                os.remove(render_package_file)

    def _revert_to_saved_scene(self):
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
