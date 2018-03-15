
class PackageEnvironment(object):

    def __init__(self, base={}):

        self._env = dict(base)

    def _set(self, name, value):
        if name in self._env and self._env[name] != value:
            raise ValueError(
                "Failed to merge different values for an exclusive environment variable:\n%s (%s\n%s)" %
                (name, self._env[name], value))
        self._env[name] = value

    def _append(self, name, value):
        if self._env.get(name):
            self._env[name] = ":".join([self._env[name], value])
        else:
            self._env[name] = value

    def extend(self, env_list):
        """"""
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

    @property
    def env(self):
        return self._env

    @env.setter
    def env(self, value):
        self._env = dict(value)
