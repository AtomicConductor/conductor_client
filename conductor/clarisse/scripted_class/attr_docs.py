def set(s_class):
    """Document all the attributes here."""


    s_class.set_attr_doc( "refresh", """Connects to Conductor and updates
     available projects and machine types. Sign in may be
        requird. Also sets empty string attributes
        to their defaults.""")

    s_class.set_attr_doc( "preview", """Opens a preview window where you can
        see the data to be submitted as JSON. You can submit directly from
        the preview window.""" )

    s_class.set_attr_doc( "submit", """Submits this job to Conductor.""" )


    s_class.set_attr_doc( "clean_up_render_package", 
        """Removes the render package file after submission.""" )

    s_class.set_attr_doc("title",
        """Sets the title that appears in the Conductor dashboard. You may use
        Clarisse variables and some Conductor variables to construct the
        title.""")

    s_class.set_attr_doc("images",
        """Sets the images to be rendered. Images must have
        their Render to Disk attribute set. The Save As field must contain
        a filename.""")

    s_class.set_attr_doc( "project", 
        """Sets the Conductor project.""")

    s_class.set_attr_doc("use_custom_frames",
        """Overrides the frame ranges from connected image nodes.""")


    s_class.set_attr_doc("custom_frames", 
        """Specifies a set of frames to render. Provide a comma-separated list
        of progressions. Example 1,7,10-20,30-60x3,1001.""")

    s_class.set_attr_doc("chunk_size", 
        """Sets the number of frames per task.""")

    s_class.set_attr_doc("use_scout_frames",
        """Activates a set of frames to scout.""")

    s_class.set_attr_doc(
        "scout_frames",
        """Scout frames to render. Tasks containing any of the specified scout
        frames, are run in their entirety. Other frames
        are set to a holding state.""")

    s_class.set_attr_doc(
        "preemptible",
        """Activates use of low-cost instances. Premptble instances may be
        stopped at any time. Check the Conductor documebtation for a
        discussion of the likelihood and situations where preemptible
        instances are suitable.""")
    s_class.set_attr_doc("instance_type", 
        """Specifies the required hardware configuration.""")
    s_class.set_attr_doc(
        "retries",
        "Sets the number of times to retry a failed task before. ")
