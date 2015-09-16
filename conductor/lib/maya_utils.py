import os
from maya import cmds

import conductor.setup

logger = conductor.setup.logger


def get_transform(shape_node):
    '''
    Return the transform node of a given shape node
    '''
    relatives = cmds.listRelatives(shape_node, parent=True, type="transform", fullPath=True) or []
    assert relatives, "Could not find parent for shape node: %s" % shape_node
    assert len(relatives) == 1, "More than one parent found for shape node: %s" % shape_node
    return relatives[0]


def get_short_name(node):
    '''
    Return the short name of a given maya node
    '''
    short_name = cmds.ls(node)
    assert short_name, "Node does not exist: %s" % node
    assert len(short_name) == 1, "More than one object matches node name: %s" % node
    return short_name[0]



def get_maya_scene_filepath():
    filepath = cmds.file(q=True, sceneName=True)
    if not filepath or not os.path.isfile(filepath):
        raise Exception("Maya scene has not been saved to a file location.  Please save file before submitting to Conductor.")
    return str(filepath)



def get_image_dirpath():
    workspace_root = cmds.workspace(q=True, rootDirectory=True)
    image_dirname = cmds.workspace(fileRuleEntry="images")
    return os.path.join(workspace_root, image_dirname)


def get_frame_range():
    '''
    Return the current frame range for the current maya scene.  This consists
    of both the "playback" start/end frames, as well as the "range" start/end frames.
    
    Note that only integers are currently support for frames
    
    return: list of two tuples, where the first tuple is the "playback" start/end 
            frames and the second is the "range" start/end frames,
            e.g. [(1.0, 24.0), (5.0, 10.0)]
    '''
    # Get the full start/end frame range
    playback_start = cmds.playbackOptions(q=True, animationStartTime=True)
    playback_end = cmds.playbackOptions(q=True, animationEndTime=True)

    # Get the selected range start/end
    range_start = cmds.playbackOptions(q=True, minTime=True)
    range_end = cmds.playbackOptions(q=True, maxTime=True)
    return [(int(playback_start), int(playback_end)), (int(range_start), int(range_end))]



def get_render_layers_info():
    '''
    TODO: Does the default render layer name need to be augmented when passed to maya's rendering command?
    TODO: Should the default render layer be included at all?  And should it be unselected by default?
    Return a list of dictionaries where each dictionary represents data for 
    a a render layer.  Each dictionar provides the following information:
        - render layer name
        - whether the render layer is set to renderable 
        - the camera that the render layer uses
    
    Note that only one camera is allowed per render layer.  This is somewhat
    of an arbitraty limitation, but implemented to reduce complexity.  This 
    restriction may need to be removed.
    
    '''
    render_layers = []
    cameras = cmds.ls(type="camera", long=True)
    for render_layer in cmds.ls(type="renderLayer"):
        layer_info = {"layer_name": render_layer}
        try:
            cmds.editRenderLayerGlobals(currentRenderLayer=render_layer)
        except RuntimeError, e:
            continue
        renderable_cameras = [get_transform(camera) for camera in cameras if cmds.getAttr("%s.renderable" % camera)]
        assert renderable_cameras, 'No Renderable camera found for render layer "%s"' % render_layer
        assert len(renderable_cameras) == 1, 'More than one renderable camera found for render layer "%s". Cameras: %s' % (render_layer, renderable_cameras)

        layer_info["camera_transform"] = renderable_cameras[0]
        layer_info["camera_shortname"] = get_short_name(layer_info["camera_transform"])
        layer_info["renderable"] = cmds.getAttr("%s.renderable" % render_layer)
        render_layers.append(layer_info)

    return render_layers


def collect_dependencies(node_attrs):
    '''
    Return a list of filepaths that the current maya scene has dependencies on.
    This is achieved by inspecting maya's nodes.  Use the node_attrs argument
    to pass in a dictionary 

    node_attrs = {'file':['fileTextureName'],
             'af_alembicDeform':['fileName'],
             'AlembicNode':['abc_File'],
             'VRayMesh':['fileName'],
             'VRaySettingsNode':['ifile', 'fnm'],
             'CrowdProxyVRay':['cacheFileDir', 'camFilePath'],
             'CrowdManagerNode':['escod', 'efbxod', 'eabcod', 'eribod', 'emrod', 'evrod', 'eassod', 'cam'],
             'xgmPalette':['.xfn']
             }

    
    '''
    assert isinstance(node_attrs, dict), "node_attrs arg must be a dict. Got %s" % type(node_attrs)

    # Note that this command will often times return filepaths with an ending "/" on it for some reason. Strip this out at the end of the function
    dependencies = cmds.file(query=True, list=True, withoutCopyNumber=True) or []

    # explicit deps
    if node_attrs is None:
        node_attrs = {'file':['fileTextureName'],
                     'af_alembicDeform':['fileName'],
                     'AlembicNode':['abc_File'],
                     'VRayMesh':['fileName'],
                     'VRaySettingsNode':['ifile', 'fnm'],
                     'CrowdProxyVRay':['cacheFileDir', 'camFilePath'],
                     'CrowdManagerNode':['escod', 'efbxod', 'eabcod', 'eribod', 'emrod', 'evrod', 'eassod', 'cam'],
                     'xgmPalette':['.xfn']
                     }

    all_node_types = cmds.allNodeTypes()

    for node_type, node_attrs in node_attrs.iteritems():

        if node_type not in all_node_types:
            logger.warning("skipping unknown node type: %s", node_type)
            continue

        for node in cmds.ls(type=node_type):
            for node_attr in node_attrs:
                plug_name = '%s.%s' % (node, node_attr)
                if cmds.objExists(plug_name):
                    plug_value = cmds.getAttr(plug_name)
                    # Note that this command will often times return filepaths with an ending "/" on it for some reason. Strip this out at the end of the function
                    path = cmds.file(plug_value, expandName=True, query=True, withoutCopyNumber=True)
                    dependencies.append(path)

    # Strip out any paths that end in "\"  or "/"    Hopefull this doesn't break anything.
    return sorted(set([path.rstrip("/\\") for path in dependencies]))


