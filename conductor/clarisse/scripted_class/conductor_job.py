import ix
import traceback

from conductor.clarisse import reloader

from conductor.clarisse.scripted_class import (dependency_ui, environment_ui,
                                               extra_uploads_ui, frames_ui,
                                               instances_ui, notifications_ui,
                                               packages_ui, projects_ui,
                                               submit_actions, variables)
from conductor.native.lib.data_block import ConductorDataBlock
from ix.api import OfAttr, OfEnum, OfObjectFactory


class ConductorJob(ix.api.ModuleScriptedClassEngine):

    def __init__(self):
        ix.api.ModuleScriptedClassEngine.__init__(self)

    def on_action(self, action, obj, data):
        """Handle any button press in the UI.

        We need to wrap everything in a try because Clarisse crashes if
        an exception is thrown from a scripted class. See
        https://www.isotropix.com/user/bugtracker/363 .
        """
        action_name = action.get_name()
        verbose_errors = obj.get_attribute("verbose_errors").get_bool()
        try:
            if action_name == "choose_packages":
                packages_ui.build(obj, data)
            elif action_name == "manage_extra_uploads":
                extra_uploads_ui.build(obj, data)
            elif action_name == "manage_extra_environment":
                environment_ui.build(obj, data)
            elif action_name == "preview":
                ConductorJob.update_from_data_block(obj)
                frames_ui.update_frame_stats_message(obj)
                submit_actions.preview(obj, data)
            elif action_name == "submit":
                ConductorJob.update_from_data_block(obj)
                frames_ui.update_frame_stats_message(obj)
                submit_actions.submit(obj, data)
            elif action_name == "refresh":
                ConductorJob.update_from_data_block(obj, force=True)
            elif action_name == "add_metadata":
                raise NotImplemented
            elif action_name == "reload":
                pass
                reload(reloader)
            else:
                pass
        except Exception as ex:
            if verbose_errors:
                ix.log_warning(traceback.format_exc())
            else:
                ix.log_warning(ex.message)

    def on_attribute_change(self, obj, attr, dirtiness, dirtiness_flags):
        """Handle attributes changing value.

        See on_action() docstring regarding exceptions.
        """

        attr_name = attr.get_name()
        verbose_errors = obj.get_attribute("verbose_errors").get_bool()
        try:
            if attr_name == "project":
                projects_ui.handle_project(obj, attr)
            elif attr_name == "use_custom_frames":
                frames_ui.handle_use_custom_frames(obj, attr)
            elif attr_name == "use_scout_frames":
                frames_ui.handle_use_scout_frames(obj, attr)
            elif attr_name == "custom_frames":
                frames_ui.handle_custom_frames(obj, attr)
            elif attr_name == "scout_frames":
                frames_ui.handle_scout_frames(obj, attr)
            elif attr_name == "progressions":
                frames_ui.handle_progressions(obj, attr)
            elif attr_name == "chunk_size":
                frames_ui.handle_chunk_size(obj, attr)
            elif attr_name == "images":
                frames_ui.handle_images(obj, attr)
            elif attr_name == "optimize_scan":
                dependency_ui.handle_optimize_scan(obj, attr)
            elif attr_name == "images":
                print "source images ref changed to:"
                pass
            elif attr_name == "notify":
                notifications_ui.notify_changed(obj, attr)
            elif attr_name == "email_addresses":
                notifications_ui.handle_email_addresses(obj, attr)
            else:
                pass
        except Exception as ex:
            if verbose_errors:
                ix.log_warning(traceback.format_exc())
            else:
                ix.log_warning(ex.message)

    def declare_attributes(self, cls):
        """All attributes and actions are declatred here.

        We don't use CID to declare these, despite it being
        reccommended, because we need better control over placement in
        the attribute editor.
        """
        variables.declare()
        self.declare_dev_attributes(cls)

        self.declare_actions(cls)
        self.declare_general_attributes(cls)
        self.declare_frames_attributes(cls)
        self.declare_machines_attributes(cls)
        self.declare_packages_attributes(cls)
        self.declare_environment_attributes(cls)
        self.declare_upload_attributes(cls)
        self.declare_task_attributes(cls)
        self.declare_notification_attributes(cls)

        ConductorJob.set_doc_strings(cls)

    def declare_dev_attributes(self, cls):

        self.add_action(cls, "reload", "development")

        attr = cls.add_attribute(
            "verbose_errors",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "development")
        attr.set_bool(False)

    def declare_actions(self, cls):
        """Attributes concerned with submission.

        Currently only buttons. These will be cleaned up and possibly
        removed.
        """

        self.add_action(cls, "preview", "actions")
        self.add_action(cls, "submit", "actions")

    def declare_general_attributes(self, cls):
        """Most commonly accessed attributes."""
        self.add_action(cls, "refresh", "general")

        attr = cls.add_attribute(
            "title",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "general")
        attr.set_expression("$PNAME")

        attr = cls.add_attribute(
            "images",
            OfAttr.TYPE_REFERENCE,
            OfAttr.CONTAINER_LIST,
            OfAttr.VISUAL_HINT_DEFAULT,
            "general")
        cs = ix.api.CoreString()
        filters = ix.api.CoreStringBasicArray(cs, 1)
        filters.set_item(0, "Image")
        attr.set_object_filters(filters)

        attr = cls.add_attribute(
            "project", OfAttr.TYPE_LONG,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "general")
        attr.set_long(0)
        attr.add_preset("- Not set -", "0")

        attr = cls.add_attribute(
            "last_project",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "general")
        attr.set_hidden(True)

    def declare_frames_attributes(self, cls):
        """All attributes concerned with the frame range to render."""

        attr = cls.add_attribute(
            "use_custom_frames",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "frames")
        attr.set_bool(False)

        attr = cls.add_attribute(
            "custom_frames",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "frames")
        attr.set_hidden(True)
        attr.set_string("2,4-8,10-50x2")

        attr = cls.add_attribute(
            "progressions",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "frames")
        attr.set_hidden(True)
        attr.set_bool(True)

        attr = cls.add_attribute(
            "chunk_size",
            OfAttr.TYPE_LONG,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "frames")
        attr.set_long(5)

        attr = cls.add_attribute(
            "use_scout_frames",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "frames")
        attr.set_bool(False)

        attr = cls.add_attribute(
            "scout_frames",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "frames")
        attr.set_hidden(True)
        attr.set_string("2,4-8,10-50x2")

        attr = cls.add_attribute(
            "frames_info",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "frames")
        attr.set_read_only(True)
        attr.set_string("- Please refresh -")

    def declare_machines_attributes(self, cls):
        """Attributes related to setting the instance type."""

        attr = cls.add_attribute(
            "preemptible",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "machines")
        attr.set_bool(True)

        attr = cls.add_attribute(
            "instance_type", OfAttr.TYPE_LONG,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "machines")
        attr.set_long(0)
        attr.add_preset("- Please refresh -", "0")

        attr = cls.add_attribute(
            "retries",
            OfAttr.TYPE_LONG,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "machines")
        attr.set_long(3)

        attr = cls.add_attribute(
            "last_instance_type",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "machines")
        attr.set_hidden(True)

    def declare_packages_attributes(self, cls):
        """Read only attribute to store package names.

        All editing of the packages list happens in the popped out UI.
        """
        self.add_action(cls, "choose_packages", "packages")

        attr = cls.add_attribute(
            "packages",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_LIST,
            OfAttr.VISUAL_HINT_DEFAULT,
            "packages")
        attr.set_read_only(True)

    def declare_task_attributes(self, cls):
        """This is the task command."""
        attr = cls.add_attribute(
            "task_template",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "task")

        expr = 'cnode "+get_string("render_package[0]")+"'
        expr += ' -image "+$CT_SOURCES+" -image_frames_list "+$CT_CHUNKS'
        attr.set_expression(expr)

    def declare_upload_attributes(self, cls):
        """Specify options for dependency scanning.

        Optimization attributes are unused right now. Extra uploads are
        managed in a pop out window.
        """

        attr = cls.add_attribute(
            "dependency_scan_policy", OfAttr.TYPE_LONG,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "upload")
        attr.set_long(0)
        attr.add_preset("No scan", "0")
        attr.add_preset("Glob sequence", "1")
        attr.add_preset("Smart sequence", "2")

        # attr = cls.add_attribute(
        #     "optimize_scan",
        #     OfAttr.TYPE_BOOL,
        #     OfAttr.CONTAINER_SINGLE,
        #     OfAttr.VISUAL_HINT_DEFAULT,
        #     "upload")
        # attr.set_bool(False)

        # attr = cls.add_attribute(
        #     "optimization_samples", OfAttr.TYPE_LONG,
        #     OfAttr.CONTAINER_SINGLE,
        #     OfAttr.VISUAL_HINT_DEFAULT,
        #     "upload")
        # attr.set_long(3)

        attr = cls.add_attribute(
            "render_package",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_FILENAME_SAVE,
            "task")
        expr = "$CDIR+\"/conductor/\"+$PNAME+\".render\""
        attr.set_expression(expr)

        self.add_action(cls, "manage_extra_uploads", "upload")
        attr = cls.add_attribute(
            "extra_uploads",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_LIST,
            OfAttr.VISUAL_HINT_DEFAULT,
            "upload")
        attr.set_read_only(True)

        attr = cls.add_attribute(
            "local_upload",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "upload")
        attr.set_bool(True)

        attr = cls.add_attribute(
            "force_upload",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "upload")
        attr.set_bool(False)

        attr = cls.add_attribute(
            "upload_only",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "upload")
        attr.set_bool(False)

    def declare_environment_attributes(self, cls):
        """Set up any extra environment.

        Vars set here will be merged with the package environments.
        """
        self.add_action(cls, "manage_extra_environment", "environment")

        attr = cls.add_attribute(
            "extra_environment",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_LIST,
            OfAttr.VISUAL_HINT_DEFAULT,
            "environment")
        attr.set_read_only(True)

    def declare_notification_attributes(self, cls):
        """Set email addresses to be notified on job completion."""
        attr = cls.add_attribute(
            "notify",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "notifications")
        attr.set_bool(False)

        attr = cls.add_attribute(
            "email_addresses",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "notifications")
        attr.set_read_only(True)

    @staticmethod
    def update_from_data_block(obj, **kw):
        """Respond to update button click.

        Update UI for projects and instances from the data block. kwargs
        may contain the force keyword, which will invalidate the
        datablock and fetch afresh from Conductor.
        """
        kw["product"] = "clarisse"
        data_block = ConductorDataBlock(**kw)
        projects_ui.update(obj, data_block)
        instances_ui.update(obj, data_block)

    @staticmethod
    def set_doc_strings(cls):
        """Document all the attributes here."""
        cls.set_attr_doc(
            "title",
            "The title that will appear in the Conductor dashboard.")
        cls.set_attr_doc(
            "source",
            "A reference to the image that will be rendered.")
        cls.set_attr_doc("project", "The Conductor project to render into.")

        cls.set_attr_doc(
            "use_custom_frames",
            "Override the frame range specified in the image node.")
        cls.set_attr_doc("custom_frames", "Frames to submit.")
        cls.set_attr_doc(
            "progressions",
            "Coerce chunks into arithmetic progressions.")
        cls.set_attr_doc("chunk_size", "Number of frames in a task.")
        cls.set_attr_doc(
            "use_scout_frames",
            "Render a subset of frames first.")
        cls.set_attr_doc(
            "scout_frames",
            "Scout frames to render. Others will be set to on-hold.")

        cls.set_attr_doc(
            "preemptible",
            "Preemptible instances are less expensive, but might be \
            interrupted and retried.")
        cls.set_attr_doc("instance_type", "Machine spec.")
        cls.set_attr_doc(
            "retries",
            "How many times to retry a failed task before giving up.")
