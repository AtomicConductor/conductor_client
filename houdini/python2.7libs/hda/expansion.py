from string import Template

class AngleBracketTemplate(Template):
    """Derived from template to allow ."""
    delimiter = '<'
    pattern = r"""
    \<(?:
    (?P<escaped>\<)|
    (?P<named>  )\>|
    (?P<braced>[a-z]+)\>|
    (?P<invalid>)
    )
    """


class Expander(object):

    def __init__(self, **kw):
        self._context = kw

    def evaluate(self, target):
        """Expand angle bracket tokens in dictionaries, lists, and strings."""
        if isinstance(target, dict):
            return {k: self.evaluate_item(v) for k, v in target.items()}
        elif isinstance(target, list):
            return [self.evaluate_item(value) for value in target]
        return self.evaluate_item(target)

    def evaluate_item(self, item):
        """Evaluate a templated string.

        Replace <token>s with values provided by the
        _context dict.

        """
        item = item.strip()
        template = AngleBracketTemplate(item)
        try:
            item = template.safe_substitute(self._context)
        except KeyError:
            raise ValueError("Invalid token %s" % item)
        return item

    @property
    def context(self):
        return self._context

    @context.setter
    def context(self, value):
        if not isinstance(value, dict):
            raise TypeError("Context must be a dict")
        self._context = value


# Render <type> -s <clumpstart> -e <clumpend> -b <clumpstep> -rl <take> -rd /tmp/render_output/ $JOB/<hipbase>_<timestamp>.hip