import traceback

import ix
from conductor.clarisse import reloader
from conductor.clarisse.clarisse_info import ClarisseInfo
from conductor.clarisse.scripted_class import (environment_ui,
                                               extra_uploads_ui, frames_ui,
                                               instances_ui, notifications_ui,
                                               packages_ui, projects_ui,
                                               submit_actions, variables)
from conductor.native.lib.data_block import ConductorDataBlock
from ix.api import OfAttr


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
                self.refresh(obj)
                submit_actions.preview(obj, data)
            elif action_name == "submit":
                self.refresh(obj)
                submit_actions.submit(obj, data)
            elif action_name == "setup":
                self.refresh(obj, force=True)
            elif action_name == "best_chunk_size":
                frames_ui.handle_best_chunk_size(obj, data)
            elif action_name == "add_metadata":
                raise NotImplementedError
            elif action_name == "reload":
                reload(reloader)
            else:
                pass
        except Exception as ex:
            if verbose_errors:
                ix.log_warning(traceback.format_exc())
            else:
                ix.log_warning(ex.message)

    def on_attribute_change(self, obj, attr, *_):
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
            elif attr_name == "chunk_size":
                frames_ui.handle_chunk_size(obj, attr)
            elif attr_name == "images":
                frames_ui.handle_images(obj, attr)
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

    def declare_attributes(self, s_class):
        """All attributes and actions are declatred here.

        We don't use CID to declare these, despite it being
        reccommended, because we need better control over placement in
        the attribute editor.
        """
        variables.declare()

        self.declare_actions(s_class)
        self.declare_general_attributes(s_class)
        self.declare_frames_attributes(s_class)
        self.declare_machines_attributes(s_class)
        self.declare_upload_attributes(s_class)
        self.declare_packages_attributes(s_class)
        self.declare_environment_attributes(s_class)
        self.declare_task_attributes(s_class)
        self.declare_notification_attributes(s_class)

        self.declare_dev_attributes(s_class)

        ConductorJob.set_doc_strings(s_class)

    def declare_dev_attributes(self, s_class):

        self.add_action(s_class, "reload", "development")

        attr = s_class.add_attribute(
            "verbose_errors",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "development")
        attr.set_bool(False)

        attr = s_class.add_attribute(
            "do_submission",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "development")
        attr.set_bool(True)

        

    def declare_actions(self, s_class):
        """Attributes concerned with submission.

        Currently only buttons.
        """

        self.add_action(s_class, "preview", "submit")
        self.add_action(s_class, "submit", "submit")

        attr = s_class.add_attribute(
            "render_package_format", OfAttr.TYPE_LONG,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "submit")
        attr.set_long(0)
        attr.add_preset("Binary archive", "0")
        attr.add_preset("Regular project", "1")

        attr = s_class.add_attribute(
            "clean_up_render_package",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "submit")
        attr.set_bool(True)

    def declare_general_attributes(self, s_class):
        """Most commonly accessed attributes."""
        self.add_action(s_class, "setup", "general")

        attr = s_class.add_attribute(
            "title",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "general")

        attr = s_class.add_attribute(
            "images",
            OfAttr.TYPE_REFERENCE,
            OfAttr.CONTAINER_LIST,
            OfAttr.VISUAL_HINT_DEFAULT,
            "general")
        cstr = ix.api.CoreString()
        filters = ix.api.CoreStringBasicArray(cstr, 1)
        filters.set_item(0, "Image")
        attr.set_object_filters(filters)

        attr = s_class.add_attribute(
            "project", OfAttr.TYPE_LONG,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "general")
        attr.set_long(0)
        attr.add_preset("- Not set -", "0")

        attr = s_class.add_attribute(
            "last_project",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "general")
        attr.set_hidden(True)

    def declare_frames_attributes(self, s_class):
        """All attributes concerned with the frame range to render."""

        attr = s_class.add_attribute(
            "use_custom_frames",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "frames")
        attr.set_bool(False)

        attr = s_class.add_attribute(
            "custom_frames",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "frames")
        attr.set_hidden(True)
        attr.set_string("2,4-8,10-50x2")

        attr = s_class.add_attribute(
            "chunk_size",
            OfAttr.TYPE_LONG,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "frames")
        attr.set_long(5)
        self.add_action(s_class, "best_chunk_size", "frames")

        attr = s_class.add_attribute(
            "use_scout_frames",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "frames")
        attr.set_bool(False)

        attr = s_class.add_attribute(
            "scout_frames",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "frames")
        attr.set_hidden(True)
        attr.set_string("2,4-8,10-50x2")

        attr = s_class.add_attribute(
            "frames_info",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "frames")
        attr.set_read_only(True)
        attr.set_string("- Please click setup -")

    def declare_machines_attributes(self, s_class):
        """Attributes related to setting the instance type."""

        attr = s_class.add_attribute(
            "preemptible",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "machines")
        attr.set_bool(True)

        attr = s_class.add_attribute(
            "instance_type", OfAttr.TYPE_LONG,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "machines")
        attr.set_long(0)
        attr.add_preset("- Please click setup -", "0")

        attr = s_class.add_attribute(
            "retries",
            OfAttr.TYPE_LONG,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "machines")
        attr.set_long(3)

        attr = s_class.add_attribute(
            "last_instance_type",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "machines")
        attr.set_hidden(True)

    def declare_upload_attributes(self, s_class):
        """Specify options for dependency scanning.

        Set to no-scan: use only cached uploads.
        Glob-scan: If filenames contain "##" or <UDIM>. They will be globbed.
        Smart-scan If filenames contain "##" the hashes will be replaced with
        frame numbers that are being used.
        """

        attr = s_class.add_attribute(
            "dependency_scan_policy", OfAttr.TYPE_LONG,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "upload")
        attr.set_long(2)
        attr.add_preset("No scan", "0")
        attr.add_preset("Glob sequence", "1")
        attr.add_preset("Smart sequence", "2")

        attr = s_class.add_attribute(
            "local_upload",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "upload")
        attr.set_bool(True)

        attr = s_class.add_attribute(
            "force_upload",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "upload")
        attr.set_bool(False)

        attr = s_class.add_attribute(
            "upload_only",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "upload")
        attr.set_bool(False)

        self.add_action(s_class, "manage_extra_uploads", "upload")

        attr = s_class.add_attribute(
            "extra_uploads",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_LIST,
            OfAttr.VISUAL_HINT_DEFAULT,
            "cached_upload_list")
        attr.set_read_only(True)

    def declare_packages_attributes(self, s_class):
        """Read only attribute to store package names.

        All editing of the packages list happens in the popped out UI.
        """
        self.add_action(s_class, "choose_packages", "packages")

        attr = s_class.add_attribute(
            "packages",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_LIST,
            OfAttr.VISUAL_HINT_DEFAULT,
            "packages")
        attr.set_read_only(True)

    def declare_task_attributes(self, s_class):
        """This is the task command template.

        It will usually contain variables that will be replaced while
        generating tasks.
        """

        s_class.add_attribute(
            "task_template",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "task")

    def declare_environment_attributes(self, s_class):
        """Set up any extra environment.

        Vars set here will be merged with the package environments.
        """
        self.add_action(s_class, "manage_extra_environment", "environment")

        attr = s_class.add_attribute(
            "extra_environment",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_LIST,
            OfAttr.VISUAL_HINT_DEFAULT,
            "environment")
        attr.set_read_only(True)

    def declare_notification_attributes(self, s_class):
        """Set email addresses to be notified on job completion."""
        attr = s_class.add_attribute(
            "notify",
            OfAttr.TYPE_BOOL,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "notifications")
        attr.set_bool(False)

        attr = s_class.add_attribute(
            "email_addresses",
            OfAttr.TYPE_STRING,
            OfAttr.CONTAINER_SINGLE,
            OfAttr.VISUAL_HINT_DEFAULT,
            "notifications")
        attr.set_read_only(True)

    @staticmethod
    def refresh(_, **kw):
        """Respond to do_setup button click.

        Update UI for projects and instances from the data block. kwargs
        may contain the force keyword, which will invalidate the
        datablock and fetch fresh from Conductor. We may as well update
        all ConductorJob nodes.
        """
        kw["product"] = "clarisse"
        data_block = ConductorDataBlock(**kw)
        nodes = ix.api.OfObjectArray()
        ix.application.get_factory().get_all_objects("ConductorJob", nodes)

        host = ClarisseInfo().get()
        detected_host_paths = data_block.package_tree().get_all_paths_to(
            **host)

        for obj in nodes:

            projects_ui.update(obj, data_block)
            instances_ui.update(obj, data_block)
            frames_ui.update_frame_stats_message(obj)

            title_attr = obj.get_attribute("title")
            if not title_attr.get_string():
                title_attr.set_expression(
                    '"Clarisse: {} "+$CT_SEQUENCE'.format(obj.get_name()))

            task_template_attr = obj.get_attribute("task_template")
            if not task_template_attr.get_string():
                expr = '"ct_cnode "+$PDIR+"/"+$PNAME+".render -image "'
                expr += '+$CT_SOURCES+" -image_frames_list "+$CT_CHUNKS +'
                expr += '" -directories "+$CT_DIRECTORIES'
                task_template_attr.set_expression(expr)
            task_template_attr.set_locked(True)

            packages_attr = obj.get_attribute("packages")
            if not packages_attr.get_value_count():
                for path in detected_host_paths:
                    packages_attr.add_string(path)

            inst_type_attr = obj.get_attribute("instance_type")
            if not inst_type_attr.get_long():
                inst_type_attr.set_long(1)

            project_attr = obj.get_attribute("project")
            if not project_attr.get_long():
                project_attr.set_long(1)

    @staticmethod
    def set_doc_strings(s_class):
        """Document all the attributes here."""

        s_class.set_attr_doc(
            "setup",
            """Press to update the available projects and machine types.
            Sign in may be required.
            This operation will also update any empty string attributes
            with sensible defaults.""")

        s_class.set_attr_doc(
            "title",
            "The title that will appear in the Conductor dashboard.")
        s_class.set_attr_doc(
            "source",
            "A reference to the image that will be rendered.")
        s_class.set_attr_doc(
            "project", "The Conductor project to render into.")

        s_class.set_attr_doc(
            "use_custom_frames",
            "Override the frame range specified in the image node.")
        s_class.set_attr_doc("custom_frames", "Frames to submit.")
        s_class.set_attr_doc("chunk_size", "Number of frames in a task.")
        s_class.set_attr_doc(
            "use_scout_frames",
            "Render a subset of frames first.")
        s_class.set_attr_doc(
            "scout_frames",
            "Scout frames to render. Others will be set to on-hold.")

        s_class.set_attr_doc(
            "preemptible",
            "Preemptible instances are less expensive, but might be \
            interrupted and retried.")
        s_class.set_attr_doc("instance_type", "Machine spec.")
        s_class.set_attr_doc(
            "retries",
            "How many times to retry a failed task before giving up.")
