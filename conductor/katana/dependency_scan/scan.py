"""Entry point: get_dependencies(). """
import re


from Katana import NodegraphAPI, FarmAPI, KatanaFile, Nodes3DAPI, Nodes2DAPI, Utils


import NodegraphAPI

# List of node_types or node_type.params to exclude.
BLACKLIST_PARAMS = ['ErrorNode',
                    'RootNode',
                    'Render',
                    'AttributeScript/user.outputPath',
                    'AttributeScript/user.outputStats',
                    'AttributeScript/user.scenePath',
                    ]

# List of files prefixes to exclude.
BLACKLIST_FILE_PRFIXES = ["/tmp/", "/var/tmp/", "/usr/tmp/", "/root/"]


def nodesUnder(node):
    """Find all descendents of the given node.

    If a Katana node has a getChildren method, it is a
    container of other nodes, so fetch those nodes in
    addition to this node.
    """
    result = [node]
    try:
        for child in node.getChildren():
            result += nodesUnder(child)
    except AttributeError:
        pass
    return result


def _flatten(param):
    """Flatten group and array parameter types.

    A parameter may contain a collection of parameters.
    Therefore, flatten them out recursively.
    """
    result = []
    if param.getType() == 'string':
        result.append(param)
    elif param.getType() in ('group', 'stringArray'):
        for child in param.getChildren():
            result += _flatten(child)
    return result


def _resolve_expression(param):
    """Resolve params whose expression evaluates to another param.

    There are two types of expression that can resolve to
    another param. They start with either getParent or
    getParam.
    """
    if param.isExpression():
        expr = param.getExpression().strip()
        if re.compile('^getParam\([ \'"0-9a-zA-Z_\.]+\)$').findall(expr):
            node_param = re.compile(
                '\([ \'"0-9a-zA-Z_\.]+\)$').findall(expr)[0]
            node_param = re.compile('[a-zA-Z0-9_.]+').findall(node_param)[0]
            node_name = node_param.split('.')[0]
            node = NodegraphAPI.GetNode(node_name)
            if node:
                param_name = '.'.join(node_param.split('.')[1:])
                new_param = node.getParameter(param_name)
                return _resolve_expression(new_param)

        elif re.compile('^getParent\(\)\.[0-9a-zA-Z_\.]+$').findall(expr):
            node = param.getNode().getParent()
            if node:
                param_name = re.compile('\.[0-9a-zA-Z_\.]+$').findall(expr)[0]
                new_param = node.getParameter(param_name.strip('.'))
                return _resolve_expression(new_param)
    return param


def _is_blacklisted(param):
    """Test param against blacklist.

    If the node type, or combination of nodetype.param is in
    the blacklist, then return True.
    """
    node = param.getNode()
    node_type = node.getType()
    if node.getParameter('user.macroType'):
        node_type = node.getParameter('user.macroType').getValue(0)
    if node_type in BLACKLIST_PARAMS:
        return True

    param_path = '%s/%s' % (node_type, param.getFullName(False))
    return param_path in BLACKLIST_PARAMS


def _is_wanted(param):
    """Various tests to determine if param can be ignored."""
    if param.getType() != 'string':
        return False
    try:
        hint = eval(param.getHintString())
        if hint.get('widget') in ['cel', 'scenegraphLocation']:
            return False
    except BaseException:
        pass
    if _is_blacklisted(param):
        return False

    return True


def _resolved_filename(param):
    """Resolve symlink and filter out blacklisted filenames."""
    filename = param.getValue(0)
    if not (
        filename and isinstance(
            filename,
            basestring) and filename.startswith("/")):
        return

    if os.path.islink(filename):
        filename = os.readlink(filename)

    for prefix in BLACKLIST_FILE_PRFIXES:
        if filename.startswith(prefix):
            return

    return filename


def _filetype(filename):
    """Get the type in lowercase.

    For now, just get the extension. Only return the type if
    the file exists.
    """
    return os.path.exists(filename) and os.path.splitext(filename)[1].lower()


def _resolve_xml_instances(instance_list):
    """Recursively expand and resolve """
    result = []
    if instance_list:
        for instance in instance_list.findall("instance"):
            if instance.attrib["type"] == "reference" and instance.attrib["refType"] == 'xml':
                inst_path = instance.attrib["refFile"]
                result.append(os.path.realpath(inst_path))
            result += _resolve_xml_instances(instance.find("instanceList"))
    return result


def _get_xml_deps(filename):
    """Get paths recursively from xml file."""
    result = []
    xml_tree = ET.parse(filename)
    xml_root = xml_tree.getroot()
    chan_data = xml_root.find("channelData")
    if chan_data:
        chan_ref = chan_data.attrib["ref"]
        if chan_ref:
            result.append(chan_ref)

    result.append(_resolve_xml_instances(xml_root.find("instanceList")))


def _debug_obj(title, obj):
    print ("=" * 10) + title + ("=" * 10)
    print obj
    print "=" * 30


def get_dependencies(node=NodegraphAPI.GetRootNode()):
    """Get dependencies of the node and its descendents."""

    print "STARTING"
    result = []
    params = _flatten(node.getParameters())
    _debug_obj(" FLATTENED ", params)
    params = list(set([_resolve_expression(param) for param in params]))
    _debug_obj(" EXPR RESOLVED ", params)

    params = [p for p in params if _is_wanted(p)]
    for p in params:
        filename = _resolve_symlink(param.getValue(0))
        if _filetype(filename) is "xml":
            result += _get_xml_deps(filename)
        else:
            result.append(filename)

    return result
