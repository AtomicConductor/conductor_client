import os
import nuke


def get_image_dirpath():
    pass

def get_nuke_version():
    '''
    Return the full version string of the currently running nuke session. 
    e.g. "9.0v5"
    '''
    return nuke.env["NukeVersionString"]

def derive_docker_image(version):
    '''
    For the given version of nuke "figure out" which docker image to use
    '''
    default_version = "9.0v7"

    versions = {"9.0v5": "nuke9.0v5",
                "9.0v7": "nuke9.0v7"}

    return versions.get(version) or default_version


def collect_dependencies(write_nodes, dependency_knobs={}):
    '''
    For the given Write nodes, traverse up their heirarchy to query any nodes
    for dependency filepaths and return them.  
    
    write_nodes: a list of Write nodes (their node names) for which to collect 
                 dependencies for.
    
    dependency_knobs: A dictioary of nuke node types (and their knob names) for 
                      which to query for dependency paths, e.g. 
                            {'Read':['file'],
                             'DeepRead':['file']}

    '''

    deps = set()

    for node_name in write_nodes:
        if nuke.exists(node_name):
            write_node = nuke.toNode(node_name)
            for dep_node in get_node_dependencies(write_node):
                for knob_name in dependency_knobs.get(dep_node.Class(), []):
                    knob = dep_node.knob(knob_name)
                    if knob:
                        deps.add(knob.value())

    return sorted(deps)


def get_node_dependencies(node, types=(), _dependencies=()):
    '''
    Recursively traverse (upwards) the given node's node graph, aggregating a list
    of all of its contributing nodes. 
    
    node: any nuke node object
    types: tuple of nuke node types (strings) to restrict the returned nodes to.  
    
    '''

    group_deps = ()
    if node.Class() == "Group":
        sub_nodes = node.nodes()
        for sub_node in sub_nodes:
            group_deps = group_deps + get_node_dependencies(sub_node, types=types,
                                                             _dependencies=_dependencies)


    parent_deps = tuple(node.dependencies())
    dependencies = ()
    for parent_dep in parent_deps:
        dependencies = dependencies + get_node_dependencies(parent_dep, types=types,
                                                        _dependencies=_dependencies)
    _dependencies = _dependencies + dependencies + tuple(parent_deps) + group_deps
    return tuple(set([d for d in _dependencies if not types or d.Class() in types]))  # TODO, if this was written properly there is probably no reason we should be getting redundant info (so no nead for a set() )




def get_nuke_script_path():
    filepath = nuke.root().name()
    if not filepath or not os.path.isfile(filepath):
        raise Exception("Nuke script has not been saved to a file location.  Please save file before submitting to Conductor.")
    return filepath

def get_frame_range():
    '''
    Return the frame range found in Nuke's Project settings.
    '''
    first_frame = int(nuke.Root()['first_frame'].value() or 0)
    last_frame = int(nuke.Root()['last_frame'].value() or 0)
    return first_frame, last_frame


def get_all_write_nodes():
    '''
    Return a dictionary of all Write and Deep Write nodes that exist in the current
    Nuke script.  The dictionary key is the node name, and the value (bool) indicates
    whether the node is currently selected or not.
    '''
    write_nodes = nuke.allNodes(filter="Write")
    write_nodes.extend(nuke.allNodes(filter="DeepWrite"))
    selected_nodes = nuke.selectedNodes()
    node_names = dict([(node.fullName(), bool(node in selected_nodes)) for node in write_nodes])
    return node_names


def get_write_node_filepath(node_name):
    '''
    For the given Write/Deepwrite node (name), return it's output filepath ("file" attr)
    If the node does not exist or it's not a write/deepwrite node, raise an exception
    '''
    write_node_types = ["Write", "DeepWrite"]
    if not nuke.exists(node_name):
        raise Exception("Write node does not exist: %s", node_name)
    node = nuke.toNode(node_name)
    if node.Class() not in write_node_types:
        raise Exception("Node not of expected types: %s. Got: %s" % (write_node_types, node.Class()))
    return node.knob("file").value()
