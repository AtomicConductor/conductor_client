
class PackageEnvironment(object):
    """Encapsulate the submission environment vars.

    Handle building up the env with a single call to extend()
    """

    def __init__(self, base=None):
        """Make the underlying dict.

        Use initial value, maybe from CONFIG, if given
        """
        self._env = dict(base or {})

    def _set(self, name, value):
        """Set the value of an exclusive variable.

        Error if it exists already and is different.
        """
        if name in self._env and self._env[name] != value:
            raise ValueError(
                """Can't overwrite environment variable: %s
                New value is:
                %s
                and it is set to exclusive. """ %
                (name, value))
        self._env[name] = value

    def _append(self, name, value):
        """Append to a variable.

        Create it if necessary, otherwise join with `:`.
        """
        if self._env.get(name):
            self._env[name] = ":".join([self._env[name], value])
        else:
            self._env[name] = value

    def extend(self, env_list):
        """Extend with the given variable specifications.

        env_list is either: A list of objects or an object
        with an "environment" key that contains a list of
        objects. Each of these objects has a name, a value,
        and a merge_policy. One by one they are added
        according to their merge policy. See set and append
        above.

        TODO: The merge policy should be set the first time a
        variable is declared and used for all subsequent
        amendments. Why? Because its more likely that
        variables are being added from packages registered
        with conductor first, and then user-defined variables
        added later. A user is more likely to make a mistake
        and corrupt a variable that has been specified in
        packages. Example: A package may set FOO=BAR
        (exclusive), but then a user may set FOO=BAZ (append).
        The result will be FOO=BAR:BAZ. The user's attempt
        should have been rejected.
        """

        try:
            others = env_list["environment"]
        except TypeError:
            others = env_list

        for var in others:
            name = var["name"]
            value = var["value"]
            policy = var["merge_policy"]
            if policy not in ["append", "exclusive"]:
                raise ValueError(
                    "Unexpected merge policy: %s" %
                    policy)

            if policy == "append":
                self._append(name, value)
            else:
                self._set(name, value)

    def __iter__(self):
        """Cast the object as a dict.

        See the tests /tests/test_package_environment.py for example
        use.
        """
        for key, val in self._env.iteritems():
            yield key, val

    def __getitem__(self, key):
        """Allow access by key."""
        return self._env.__getitem__(key)
