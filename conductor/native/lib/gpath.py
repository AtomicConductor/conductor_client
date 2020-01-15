import os

import re

RX_LETTER = re.compile(r"^([a-zA-Z]):")
RX_DOLLAR_VAR = re.compile(r"\$([A-Za-z][A-Z,a-z0-9_]+)")


def _expand_context(path, context):
    result = path
    if context:
        for match in RX_DOLLAR_VAR.finditer(path):
            key = match.group(1)
            replacement = context.get(key)
            if replacement is not None:
                result = result.replace("${}".format(key), replacement)
    return result


def _normalize_dots(components):
    currentdir = "."
    parentdir = ".."
    result = []
    for c in components:
        if c == currentdir:
            pass
        elif c == parentdir:
            if not len(result):
                raise ValueError("Can't resolve components due to '..' overflow:")
            del result[-1]
        else:
            result.append(c)
    return result


class Path(object):
    def __init__(self, path, **kw):
        """Initialize a generic absolute path.

        If path is a list, then each element will be a component of the path. 
        If it's a string then expand context variables.
        Also expand, env vars and user unless explicitly told not to with the
        no_expand option. 
        """

        if not path:
            raise ValueError("Empty path")

        if isinstance(path, list):
            ipath = path[:]
            self._drive_letter = ipath.pop(0)[0] if RX_LETTER.match(ipath[0]) else None
            self._components = _normalize_dots(ipath)
            self._absolute = True
        else:
            context = kw.get("context")
            if context:
                path = _expand_context(path, context)

            if not kw.get("no_expand", False):
                path = os.path.expanduser(os.path.expandvars(path))

            match = RX_LETTER.match(path)
            self._drive_letter = match.group(1) if match else None
            remainder = re.sub(RX_LETTER, "", path)

            self._absolute = remainder[0] in ["/", "\\"]

            if ":" in remainder:
                raise ValueError("Bad characters in path '{}'".format(remainder))

            self._components = _normalize_dots(
                [s for s in re.split("/|\\\\", remainder) if s]
            )

        self._depth = len(self._components)

    def _construct_path(self, sep, with_drive_letter=True):
        """Reconstruct path for given path sep."""
        result = sep.join(self._components)
        if self._absolute:
            result = "{}{}".format(sep, result)
        if with_drive_letter and self._drive_letter:
            result = "{}:{}".format(self._drive_letter, result)
        return result

    def posix_path(self, **kw):
        """Path with forward slashes. Can include drive letter."""
        with_drive_letter = kw.get("with_drive", True)
        return self._construct_path("/", with_drive_letter)

    def windows_path(self, **kw):
        """Path with back slashes. Can include drive letter."""
        with_drive_letter = kw.get("with_drive", True)
        return self._construct_path("\\", with_drive_letter)

    def os_path(self, **kw):
        """Path with slashes for current os. Can include drive letter."""
        with_drive = kw.get("with_drive", True)
        if os.name == "nt":
            return self.windows_path(with_drive=with_drive)
        return self.posix_path(with_drive=with_drive)

    def startswith(self, path):
        return self.posix_path().startswith(path.posix_path())

    def endswith(self, suffix):
        return self.posix_path().endswith(suffix)

    def __len__(self):
        return len(self.posix_path())

    def __eq__(self, rhs):
        if not isinstance(rhs, Path):
            raise NotImplementedError
        return self.posix_path() == rhs.posix_path()

    def __ne__(self, rhs):
        return not self == rhs

    @property
    def depth(self):
        return self._depth

    @property
    def drive_letter(self):
        return self._drive_letter or ""

    @property
    def absolute(self):
        return self._absolute

    @property
    def relative(self):
        return not self._absolute

    @property
    def components(self):
        return self._components or []

    @property
    def all_components(self):
        if self.drive_letter:
            return ["{}:".format(self.drive_letter)] + self.components
        else:
            return self.components

    @property
    def tail(self):
        return self._components[-1] if self._components else None
