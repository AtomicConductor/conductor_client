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

def get_plugins():
    '''
    TODO:(lws) WIP - there has to be better way of doing this.  
    
    Return the plugins from the current Nuke session. This is a list of filepaths
    to each nuke plugin. ugly
    
        ['/home/nuke/tools/customCG_Neutralize.gizmo',
        '/home/nuke/tools/customCG_deNeutralize.gizmo',
        '/home/nuke/tools/customCameraShake.gizmo',
        '/home/nuke/tools/customChromaticAbberation.gizmo',
        '/home/nuke/tools/customGlint.gizmo',
        '/home/nuke/tools/customGrain.gizmo',
        '/home/nuke/tools/customHaze.gizmo',
        '/home/nuke/tools/custom_OutputCrop.gizmo',
        '/home/nuke/tools/gizmos/default_viewer.gizmo',
        '/home/nuke/tools/nuke/init.py',
        '/home/nuke/nuke/linux64/Nuke9.0/GeoPoints.so',
        '/home/nuke/nuke/linux64/Nuke9.0/LD_3DE4_Anamorphic_Degree_6.so',
        '/home/nuke/nuke/linux64/Nuke9.0/OpticalFlares.so',
        '/home/nuke/nuke/linux64/Nuke9.0/pgBokeh.so',
        '/home/nuke/nuke/linux64/Nuke9.0/render',
        '/home/nuke/nuke/linux64/Nuke9.0/starpro.key',
        '/home/nuke/.nuke/MTTF',
        '/home/nuke/.nuke/ScriptEditorHistory.xml',
        '/home/nuke/.nuke/layout1.xml',
        '/home/nuke/.nuke/preferences8.0.nk',
        '/home/nuke/.nuke/recent_files',
        '/home/nuke/.nuke/uistate.ini',
        '/home/nuke/.nuke/user.9-0.hrox',
        '/home/neatvideo/neat_video_ofx/NeatVideo.ofx.bundle/Contents/Linux-x86-64/NeatVideo.ofx']
        
    '''

    # If you don't specify the nuke.ALL flag, you end up with paths to icon files
    # (png, etg), instead of the actual plugin (.so, .py, etc). However, when specifying
    # nuke.ALL it also returns plugins that are not currently loaded, which we
    # probably don't want. I assume we want to only return plugins that are
    # currently in use, otherwise our docker image requirements become far more
    # comprehensive (demanding) than they need to be. So we use the
    # nuke.pluginExists() on each plugin, to determine if the plugin is loaded.
    # I have no idea if the this is a the best way (or even a reliable way) to
    # determine if a plugin is loaded or not, but I couldn't find a better function.
    # It did however cut down the returned plugins by 10  (54 to 44).
    # Note that we gather the fullpaths bc it's possible that there could be
    # naming conflicts/overlaps between plugins.
    # Exclude any plugins that are located within Nuke's installation directory.
    # We'll assume those are standarad plugins that Nuke ships with. Perhaps
    # a bad assumption, but we'll go with it for now.
    plugins = []
    nuke_dirpath = os.path.dirname(nuke.EXE_PATH)
    for p in nuke.plugins(nuke.ALL):
        if nuke.pluginExists(p) and not p.startswith(nuke_dirpath):
            plugins.append(p)
    return plugins


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
