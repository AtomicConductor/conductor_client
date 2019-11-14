"""
Responds to events in the  upload section of the ConductorJob attribute editor.
"""

import ix


def handle_local_upload(obj, attr):
    """
    Responds to local_upload changes.

    We must not clean up the render file if local_upload is false,
    because it cleans up before the upload daemon has had a chance
    to upload it.

    Args:
        obj (ConductorJob):
        attr (OfAttr): Attribute that changed.
    """
    obj.get_attribute("clean_up_render_package").set_hidden(not attr.get_bool())
