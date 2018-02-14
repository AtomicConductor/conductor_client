import re

"""Very simple loose email regex."""
SIMPLE_EMAIL_RE = re.compile(r"^\S+@\S+$")


def validate_emails(node, **kw):
    """Emails must all be somewhat valid.

    Otherwise disable `valid` tickmark

    """
    result = True
    val = node.parm("email_addresses").eval().strip(',').strip()

    if not bool(val):
        result = False
    else:
        for address in [x.strip() for x in val.split(',')]:
            if not (SIMPLE_EMAIL_RE.match(address)):
                result = False
                break
    node.parm("email_valid").set(result)


def email_hook_changed(node, **kw):
    """If no email hooks selected then dim out the email field.

    Get the child toggles of the hooks folder dynamically
    rather than list them explicitly. In this way, other
    hooks can be added with minimum fuss.

    """
    result = 0
    template = node.type().definition().parmTemplateGroup().find('hooks')
    hooks = [p.name() for p in template.parmTemplates()
             if p.type().name() == "Toggle"]
    for hook in hooks:
        if node.parm(hook).eval():
            result = 1
            break
    node.parm("do_email").set(result)
