"""
Provide UI to specify what events to notify users of.

Currently only email notifications.
"""

import re

import ix

# Simple loose email regex, matches 1 email address.
SIMPLE_EMAIL_RE = re.compile(r"^\S+@\S+$")


def handle_email_addresses(obj, _):
    """
    Validate email addresses when attribute changes.

    Args:
        obj (ConductorJob): Item from which to get notification data
    """
    val = obj.get_attribute("email_addresses").get_string().strip(",").strip()
    result = bool(val)
    for address in [x.strip() for x in val.split(",")]:
        if not SIMPLE_EMAIL_RE.match(address):
            result = False
            break
    if not result:
        ix.log_warning("Email addresses are invalid.")


def notify_changed(obj, attr):
    """
    Dim the email field based on toggle value.

    Args:
        obj (ConductorJob): Item in question
        attr (OfAttr): The toggle attribute
    """
    obj.get_attribute("email_addresses").set_read_only(not attr.get_bool())
