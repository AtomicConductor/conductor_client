"""Purpose of this module is to mock Houdini's hou namespace.

It is intended to be called from tests, and those test
modules are responsible for replacing
sys.modules['hou'] with this module.

# something like this
sys.modules['hou'] = __import__(
    'conductor.houdini.lib.mocks.hou', fromlist=['dummy'])
"""

from conductor.native.lib.sequence import Sequence

NODES = {}
NODE_TYPES = {}
FILES = []
GVARS = {}


class NodeType(object):
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class Parm(object):
    def __init__(self, node, parm_obj):
        self._name = parm_obj["name"]
        self._value = parm_obj["value"]
        self._node = node

    def name(self):
        return self._name

    def node(self):
        return self._node

    def unexpandedString(self):
        return self._value

    def eval(self):
        return self.evalAtFrame(1)

    def evalAtFrame(self, frame):
        kw = {
            "os": self.node().name(),
            "f": frame,
            "f1": frame,
            "f2": "%02d" % frame,
            "f3": "%03d" % frame,
            "f4": "%04d" % frame
        }
        return expand(self._value, **kw)


class Node(object):

    def __init__(self, node_obj):
        self._name = node_obj["name"]
        self._type = NODE_TYPES[node_obj["type"]]
        self._parms = {}
        for parm in node_obj["parms"]:
            self._parms[parm["name"]] = Parm(self, parm)

    def name(self):
        return self._name

    def type(self):
        return self._type

    def parm(self, parm_name):
        return self._parms.get(parm_name)

    def parms(self):
        return self._parms


class OperationFailed(Exception):
    """Mock hou.OperationFailed.

    Needed by houdini calls in
    """

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)


def expand(template, **kw):
    kw.update(GVARS)
    keys = sorted(kw.keys(), key=lambda key: -len(key))
    for k in keys:
        value = kw[k]
        template = template.replace("$%s" % k.upper(), str(value))
    return template


def node(name):
    return NODES.get(name)


def fileReferences():
    result = []
    for n in NODES:
        parms = NODES[n].parms()
        for p in parms:
            result.append((parms[p], parms[p].eval()))

    return result


def _find_on_disk(path, ftype):
    for f in FILES:
        if path == f["path"]:
            if f["type"] == ftype:
                return path
            else:
                break
    raise OperationFailed()


def findFile(path):
    return _find_on_disk(path, "f")


def findDirectory(path):
    return _find_on_disk(path, "d")


def initialize(data):
    """Generate nodes, types, and files from fixture data."""
    global NODES
    global NODE_TYPES
    global FILES
    global GVARS

    GVARS.update(data["gvars"])

    type_names = list(set([n["type"] for n in data["nodes"]]))
    for t in type_names:
        NODE_TYPES[t] = NodeType(t)

    for item in data["nodes"]:
        NODES[item["name"]] = Node(item)

    for item in data["files"]:
        if item.get("params"):
            for fn in Sequence.permutations(item["path"], **item["params"]):
                FILES.append({"path": fn, "type": item["type"]})
        else:
            FILES.append(item)
