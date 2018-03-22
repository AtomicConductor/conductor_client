

class ConductorDataBlock:

    instance = None

    class __ConductorDataBlock:

        def __init__(self):

            self._projects = ["foo", "bar"]
            self._instances = ["foo", "maz"]
            self._packages = ["foo", "ohn"]

        # def set_projects(self, **kw):
        #     pass
        # def set_instancess(self, **kw):
        #     pass
        # def set_packagess(self, **kw):
        #     pass

            # self.val = arg
        def __str__(self):
            return repr(self)

        # @property
        # def projects(self):
        #     return self._projects

        # @property
        # def instances(self):
        #     return self._instances

        # @property
        def packages(self):
            return self._packages

        # @projects.setter
        # def projects(self, value):
        #     self._projects = value

        # @instances.setter
        # def instances(self, value):
        #     self._instances = value

        # @packages.setter
        def set_packages(self, value):
            self._packages = value

    def __init__(self):
        if not ConductorDataBlock.instance:
            ConductorDataBlock.instance = ConductorDataBlock.__ConductorDataBlock()

    def __getattr__(self, name):
        return getattr(self.instance, name)

        # else:
        #     ConductorDataBlock.instance.set(**kw)

    # def __getattr__(self, name):
    #     return getattr(self.instance, name)


db = ConductorDataBlock()

print db.packages()


db2 = ConductorDataBlock()

db2.set_packages({"bof": "gon"})

print db.packages()

print db
print db2
