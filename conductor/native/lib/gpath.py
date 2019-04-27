
import os
import re

LETTER_RE = re.compile(r'^([a-zA-Z]):')


class GPathError(Exception):
    pass


class Path(object):

    def __init__(self, path):
        """Initialize a generic absolute path.

        If path is a list, then each element will be a component of the path. 
        If it's a string then expand variables and user. 
        """

        if not path:
            raise GPathError("Empty path")

        if isinstance(path, list):
            ipath = path[:]
            self._drive_letter = ipath.pop(
                0)[0] if LETTER_RE.match(ipath[0]) else None
            self._components = ipath
        else:
            path = os.path.expanduser(os.path.expandvars(path))

            match = LETTER_RE.match(path)
            self._drive_letter = match.group(1) if match else None
            remainder = re.sub(LETTER_RE, "", path)

            if remainder[0] not in ["/", "\\"]:
                raise GPathError("Not an absolute path")

            if any((c in [":"]) for c in remainder):
                raise GPathError("Bad characters in path")

            self._components = [s for s in re.split('/|\\\\', remainder) if s]

        self._depth = len(self._components)

    def _construct_path(self, sep, with_drive_letter=True):
        """Reconstruct path for given path sep."""
        result = "{}{}".format(sep, sep.join(self._components))
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

    def os_path(self,  **kw):
        """Path with slashes for current os. Can include drive letter."""
        with_drive = kw.get("with_drive", True)
        if os.name == "nt":
            return self.windows_path(with_drive=with_drive)
        return self.posix_path(with_drive=with_drive)

    def startswith(self, path):
        return self.posix_path().startswith(path.posix_path())

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
        return self._components[-1]
