
def set(s_class):
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
