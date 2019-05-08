"""Build an object to represent a Clarisse Conductor submission."""

import datetime
import os
import sys
import traceback

import ix
from conductor.clarisse.scripted_class import frames_ui, variables
from conductor.clarisse.scripted_class.job import Job
from conductor.lib import conductor_submit
from conductor.native.lib.data_block import ConductorDataBlock
from conductor.native.lib.gpath import Path


def _localize_contexts():
    """Make all clarisse reference contexts local.

    This is the equivalent of importing Maya references.
    """
    contexts = ix.api.OfContextSet()
    ix.application.get_factory().get_root().resolve_all_contexts(contexts)
    for ctx in contexts:
        if ctx.is_reference():
            path = ctx.get_attribute("filename").get_string()
            fn, ext = os.path.splitext(path)
            if ext == ".project":
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
    variables.remove()


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
        setenv(). After _setenv has been called, the Submission level
        token variables are valid and calls to evaluate expressions will
        correctly resolve where those tokens have been used.
        """

        self.node = obj

        if self.node.is_kindof("ConductorJob"):
            self.nodes = [obj]
        else:
            raise NotImplementedError

        self.project_filename = ix.application.get_current_project_filename()
        self.timestamp = datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
        self.render_package = self._get_render_package()
        self.delete_render_package = self.node.get_attribute(
            "clean_up_render_package").get_bool()

        self.local_upload = self.node.get_attribute("local_upload").get_bool()
        self.force_upload = self.node.get_attribute("force_upload").get_bool()
        self.upload_only = self.node.get_attribute("upload_only").get_bool()
        self.project = self._get_project()
        self.notifications = self._get_notifications()

        self.tokens = self._setenv()

        self.jobs = []
        for node in self.nodes:
            job = Job(node, self.tokens, self.render_package)
            self.jobs.append(job)

    def _get_project(self):
        """Get the project from the attr.

        Get its ID in case the current project is no longer in the list
        of projects at conductor, throw an error.
        """

        projects = ConductorDataBlock().projects()
        project_att = self.node.get_attribute("project")
        label = project_att.get_applied_preset_label()

        try:
            found = next(p for p in projects if str(p["name"]) == label)
        except StopIteration:
            ix.log_error(
                "Cannot find project \"{}\" at Conductor.".format(label))
        return {
            "id": found["id"],
            "name": str(found["name"])
        }

    def _get_notifications(self):
        """Get notification prefs."""
        if not self.node.get_attribute("notify").get_bool():
            return None

        result = {"email": {}}
        address_val = self.node.get_attribute("email_addresses").get_string()

        result["email"]["addresses"] = []
        for email in address_val.split(","):
            if email:
                result["email"]["addresses"].append(email.strip())

        return result

    def _setenv(self):
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
        tokens["CT_PDIR"] = Path(
            variables.get("PDIR")).posix_path(
            with_drive=False)

        tokens["CT_SCRIPT_DIR"] = Path(
            "$CONDUCTOR_LOCATION/conductor/clarisse/scripts").posix_path(with_drive=False)
        tokens["CT_TIMESTAMP"] = self.timestamp
        tokens["CT_SUBMITTER"] = self.node.get_name()
        tokens["CT_RENDER_PACKAGE"] = self.render_package.posix_path(
            with_drive=False)
        tokens["CT_PROJECT"] = self.project["name"]

        for token in tokens:
            variables.put(token, tokens[token])

        return tokens

    def _get_render_package(self):
        basename = os.path.splitext(
            ix.application.get_current_project_filename())[0]

        return Path("{}.render".format(basename))

    def get_args(self):
        """Prepare the args for submission to conductor.

        This is a list where there is one args object for each Conductor
        job. The project, notifications, and upload args are the same
        for all jobs, so they are set here. Other args are provided by
        Job objects and updated with these submission level args to form
        each complete job submissions.
        """
        result = []
        submission_args = {}

        submission_args["local_upload"] = self.local_upload
        submission_args["upload_only"] = self.upload_only
        submission_args["force"] = self.force_upload
        submission_args["project"] = self.project["name"]

        if self.email_addresses:
            addresses = ", ".join(self.email_addresses)
            submission_args["notify"] = {"emails": addresses}
        else:
            submission_args["notify"] = []

        for job in self.jobs:
            args = job.get_args()
            args.update(submission_args)
            result.append(args)
        return result

    def submit(self):
        """Submit all jobs.

        Collect responses and show them in the log.
        """

        self.write_render_package()

        results = []
        for job_args in self.get_args():
            try:
                remote_job = conductor_submit.Submit(job_args)
                response, response_code = remote_job.main()
                results.append(
                    {"code": response_code, "response": response})
            except BaseException:
                results.append({"code": "undefined", "response": "".join(
                    traceback.format_exception(*sys.exc_info()))})
        for result in results:
            ix.log_info(result)

        self._post_submit()

    def write_render_package(self):
        """Write a package suitable for rendering.

        A render package is a binary package designed for rendering. It
        has the same name as the project, but with .render for the
        extension. It is a binary, around half the size of a project
        file. Before saving, all reference contexts are made local, and
        all Conductor data is removed.
        """

        app = ix.application
        self._pre_write_package()

        package_file = self.render_package.posix_path()
        success = app.export_render_archive(package_file)

        if os.environ.get("CONDUCTOR_MODE") == "dev":
            filename = os.path.join(
                os.path.dirname(
                    app.get_current_project_filename()),
                "ct_debug.project")
            app.disable()
            app.save_project_snapshot(filename)
            app.enable()

        self._post_write_package()

        if not success:
            ix.log_error(
                "Failed to export render package {}".format(package_file))

        ix.log_info("Wrote package to {}".format(package_file))
        return package_file

    def _pre_write_package(self):
        self._ensure_valid_image_ranges()
        _localize_contexts()
        _remove_conductor()

    def _ensure_valid_image_ranges(self):
        """Fix image ranges to make them renderable.

        For any job node that has custom frames, we need to make sure
        the image node covers those frames, otherwise it won't render. I
        believe this is a failing on the part of Clarisse. If you
        specify a frame to render on the command line, it should be
        rendered even if it is not within the range specified on the
        image node.
        """
        for node in self.nodes:
            if node.get_attribute("use_custom_frames").get_bool():
                seq = frames_ui.custom_frame_sequence(node)
                images = ix.api.OfObjectArray()
                node.get_attribute("images").get_values(images)
                for image in images:
                    frames_ui.set_image_range(image, seq)

    def _post_submit(self):
        self._do_delete_render_package()

    def _post_write_package(self):
        """Cleanup."""
        self._revert_to_saved_scene()

    def _do_delete_render_package(self):
        if self.delete_render_package:
            render_package_file = self.render_package.posix_path()
            if os.path.exists(render_package_file):
                os.remove(render_package_file)

    def _revert_to_saved_scene(self):
        clarisse_win = ix.application.get_event_window()
        old_cursor = clarisse_win.get_mouse_cursor()
        clarisse_win.set_mouse_cursor(ix.api.Gui.MOUSE_CURSOR_WAIT)
        ix.application.disable()
        ix.application.load_project(self.project_filename)
        ix.application.enable()
        clarisse_win.set_mouse_cursor(old_cursor)

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
