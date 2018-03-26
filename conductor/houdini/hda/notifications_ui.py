"""Provide UI to specify what events to notify users of.

Currently only email notifications.
"""

import re

# Simple loose email regex, matches 1 email address.
SIMPLE_EMAIL_RE = re.compile(r"^\S+@\S+$")


def validate_emails(node, **_):
    """Emails must all be somewhat valid.

    Split the list of emails and loop through. Disable
    `valid` tickmark if any matches fail.
    """

    val = node.parm("email_addresses").eval().strip(',').strip()
    result = bool(val)
    for address in [x.strip() for x in val.split(',')]:
        if not SIMPLE_EMAIL_RE.match(address):
            result = False
            break
    node.parm("email_valid").set(result)


def _get_hook_parm_names(node):
    """Get parm names for hooks.

    Gets all email hook toggles in the notifications folder.
    """
    template = node.type().definition().parmTemplateGroup().find('notifications')
    return [p.name() for p in template.parmTemplates()
            if p.type().name() == "Toggle" and p.name().startswith("email_on")]


def email_hook_changed(node, **_):
    """If no email hooks selected then dim out the email field."""
    result = 0
    for hook in _get_hook_parm_names(node):
        if node.parm(hook).eval():
            result = 1
            break
    node.parm("do_email").set(result)


def get_notifications(node):
    """Build a notification dict.

    This object specifies addresses, hooks, and in future IM
    channels etc.
    """
    if not node.parm("do_email").eval():
        return None
    result = {"email": {}}
    address_val = node.parm("email_addresses").eval()
    result["email"]["addresses"] = [email.strip()
                                    for email in address_val.split(",") if email]
    hook_names = _get_hook_parm_names(node)
    result["email"]["hooks"] = [
        (hook, bool(node.parm(hook).eval())) for hook in hook_names]
    return result
