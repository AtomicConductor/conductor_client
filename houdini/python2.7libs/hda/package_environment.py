
class PackageEnvironment(object):

    def __init__(self, base={}):
 
        self._env =  dict(base)

    # def __radd__(self, other):
    #     if not other:
    #         return self.env
    #     # Other will be an array of environments

    #     for env in other:


    def extend(self, other):

        if other:
            for var in other:
                name = var["name"]
                value = var["value"]
                policy = var["merge_policy"]
                if policy not in ["append", "exclusive"]:
                    raise ValueError("Unexpected merge policy: %s" % merge_policy)

                if policy == "append":
                     self._env[name] = ":".join([self._env[name], value]) if self._env.get(name) else value
                else:
                     if name in self._env and self._env[name] != value:
                         raise ValueError("Failed to merge different values for an exclusive environment variable:\n%s "
                                         "(%s\n%s)"  % (name, env[name], value))
                     self._env[name] = value





 def merge_package_environments(packages, base_env=None):
     '''
     For the given conductor software packages, resolve and merge their environements
     int one single dictionary.

     Merge policies:
         append: appends values, separated by colons
         exclusive: indicates that
     '''
     env = dict(base_env or {})  # Make a copy of the dict. Don't want to alter original
     for package in packages:
 #         logger.debug("package: %s", package)
         for env_variable in package.get("environment", []):
             name = env_variable["name"]
             value = env_variable["value"]
             merge_policy = env_variable["merge_policy"]

             ### APPEND ###
             if merge_policy == "append":
                 env[name] = ":".join([env[name], value]) if  env.get(name) else value

             ### EXCLUSIVE ###
             elif merge_policy == "exclusive":
                 if name in  env and env[name] != value:
                     raise Exception("Could not merge package environments due to "
                                     "difference in exclusive environment variable: %s "
                                     "(%s vs %s)\n"
                                     "Packages:\n\t%s" % (name,
                                                          env[name],
                                                          value,
                                                          "\n\t".join([pformat(p) for p in packages])))
                 env[name] = value

             else:
                 raise Exception("Got unexpected merge policy: %s" % merge_policy)
     return env



