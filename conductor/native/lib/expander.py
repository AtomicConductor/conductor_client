
import os
import re
from string import Template


class AngleBracketTemplate(Template):
    """ Template for substituting tokens in angle brackets.

    Tokens may have lowercase letters and contain underscores.
    E.g. <foo> or <foo_bar>
    """
    delimiter = '<'
    pattern = r"""
        \<(?:
        (?P<escaped>\<)|
        (?P<named>  )\>|
        (?P<braced>[a-z][a-z_]+)\>|
        (?P<invalid>)
        )
        """


class Expander(object):
    """Class to expand angle bracket tokens."""

    def __init__(self, **context):
        self._context = context

    def evaluate(self, target):
        """Evaluate target, whether its a value, list, or dict."""
        if type(target) == dict:
            result = {}
            for k in target:
                result[k] = self.evaluate_item(target[k])
            return result
        elif type(target) == list:
            return [self.evaluate_item(value) for value in target]
        return self.evaluate_item(target)

    def evaluate_item(self, item):
        """Evaluate an expression string

        Replace <token>s with values provided by the _context dict
        """
        try:
            return AngleBracketTemplate(item.strip()).substitute(self._context)
        except KeyError:
            raise KeyError("Invalid token. Valid tokens are: {}".format(
                self._context.keys()))
