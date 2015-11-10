import os, re, yaml
import functools
from maya import cmds

import conductor.setup

logger = conductor.setup.logger
dependency_attrs = {'file':['fileTextureName'],
                     'af_alembicDeform':['fileName'],
                     'AlembicNode':['abc_File'],
                     'VRayMesh':['fileName'],
                     'VRaySettingsNode':['ifile', 'fnm'],
                     'CrowdProxyVRay':['cacheFileDir', 'camFilePath'],
                     'CrowdManagerNode':['escod', 'efbxod', 'eabcod', 'eribod', 'emrod', 'evrod', 'eassod', 'cam'],
                     'xgmPalette':['xfn'],
                     'VRayVolumeGrid':['if']
                    }

def dec_undo(func):
    '''
    DECORATOR - Wrap the decorated function in a Maya undo block.  
    This is useful when wrapping functions which execute multiple maya commands,
    thereby altering maya's state and undo stack with multiple operations.  
    This allows the artis to simply execute one undo call to undo all of the 
    calls that this wrapped function executed (as opposed to having the artist
    press undo undo undo undo..etc) 
    '''
    @functools.wraps(func)
    def wrapper(*a, **kw):
        cmds.undoInfo(openChunk=True)
        try:
            return func(*a, **kw)
        finally:
            cmds.undoInfo(closeChunk=True)
    return wrapper


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


def get_maya_version():
    '''
    Return the version string of the currently running maya session. 
    e.g. "2015"
    '''
    return cmds.about(version=True)


def get_plugin_versions():
    '''
    Query maya for all of it's plugins and their  versions. 
    
    return a dictionary such as:
        {'AbcExport': '1.0',
         'AbcImport': '1.0',
         'BifrostMain': '1.0',
         'HoldOut': '1.0',
         'MayaMuscle': '2.00 (Build: 004)',
         'Mayatomr': '2015.0 - 3.12.1.18 ',
         'Substance': '1.11143',
         'autoLoader': '1.0',
         'bifrostshellnode': '2015',
         'bifrostvisplugin': '3.0',
         'cgfxShader': 'cgfxShader 4.5 for Maya 2015.0 (Apr  9 2015)',
         'fbxmaya': '2015.1',
         'glmCrowd': '4.1.3[21f4d33]-2015/08/25',
         'gpuCache': '1.0',
         'iDeform': '1.0',
         'ik2Bsolver': '2.5',
         'ikSpringSolver': '1.0',
         'matrixNodes': '1.0',
         'mayaCharacterization': '5',
         'mayaHIK': '1.0_HIK_2014.2',
         'modelingToolkit': 'Unknown',
         'modelingToolkitStd': '0.0.0.0',
         'quatNodes': '1.0',
         'relax_node': 'Unknown',
         'retargeterNodes': '1.0',
         'rotateHelper': '1.0',
         'sceneAssembly': '1.0',
         'shaderFXPlugin': '1.0',
         'skinningDecomposition': '1.0',
         'spReticleLoc': '2.0',
         'tiffFloatReader': '8.0',
         'vrayformaya': '3.00.01',
         'xgenMR': '1.0',
         'xgenToolkit': '1.0'}
    
    '''
    plugin_versions = {}
    for plugin in cmds.pluginInfo(q=True, listPlugins=True):
        plugin_versions[str(plugin)] = str(cmds.pluginInfo(plugin, version=True, q=True))
    return plugin_versions



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


@dec_undo
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
    
    Note that this function is wrapped in an undo block because it actually changes
    the state of the maya session (unfortuantely). There doesn't appear to be
    an available api call to query maya for this information, without changing
    it's state (switching the active render layer)
    '''
    render_layers = []
    cameras = cmds.ls(type="camera", long=True)

    # record the original render layer so that we can set it back later. Wow this sucks
    original_render_layer = cmds.editRenderLayerGlobals(currentRenderLayer=True, q=True)
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

    # reinstate the original render layer as the active render layer
    cmds.editRenderLayerGlobals(currentRenderLayer=original_render_layer)
    return render_layers


def collect_dependencies(node_attrs):
    '''
    Return a list of filepaths that the current maya scene has dependencies on.
    This is achieved by inspecting maya's nodes.  Use the node_attrs argument
    to pass in a dictionary 
    '''
    assert isinstance(node_attrs, dict), "node_attrs arg must be a dict. Got %s" % type(node_attrs)

    # Note that this command will often times return filepaths with an ending "/" on it for some reason. Strip this out at the end of the function
    dependencies = cmds.file(query=True, list=True, withoutCopyNumber=True) or []

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

                    #  For xgen files, read the .xgen file and parse out the directory where other dependencies may exist
                    if node_type == "xgmPalette":
                        sceneFile = cmds.file(query=True, sceneName=True)
                        path = os.path.join(os.path.dirname(sceneFile), plug_value)
                        dependencies += parse_xgen_file(path, node)

                    dependencies.append(path)

    #  Grab any OCIO settings that might be there...
    ocio_config = get_ocio_config()
    if ocio_config:
        logger.info("OCIO config detected -- %s" % ocio_config)
        dependencies.append(ocio_config)
        dependencies.append(parse_ocio_config(ocio_config))


    # Strip out any paths that end in "\"  or "/"    Hopefull this doesn't break anything.
    return sorted(set([path.rstrip("/\\") for path in dependencies]))

def get_ocio_config():
    plug_name = "defaultColorMgtGlobals.cfp"
    if cmds.objExists(plug_name):
        return cmds.getAttr(plug_name)

#  Parse the xgen file to find the paths for extra dependencies not explicitly
#  named. This will return a list of files and directories.
def parse_xgen_file(path, node):
    file_paths = []
    m = re.match("(.+)\.xgen", path)
    if m:
        abc_patch_file = cmds.file("%s.abc" % (m.group(1)), expandName=True, query=True, withoutCopyNumber=True)
        if os.path.isfile(abc_patch_file):
            file_paths.append(abc_patch_file)

    paletteSection = False
    project_dir = ""
    local_file = ""
    fp = open(path, "r")
    for line in fp:
        m = re.match("^Palette$", line)
        if m:
            paletteSection = True
            continue

        if paletteSection:
            print line
            m = re.match("^\w", line)
            if m:
                file_path = os.path.join(project_dir, local_file)
                file_paths.append(file_path)

                paletteSection = False
                local_file = ""
                project_dir = ""
                continue

            m = re.match("\s*xgDataPath\s+(.+/%s)" % node, line)
            if m:
                local_file = m.group(1)
                local_file = re.sub("\$\{PROJECT\}", "", local_file)
                continue

            m = re.match("\s*xgProjectPath\s+(.+)", line)
            if m:
                project_dir = m.group(1)
                continue

    return file_paths

#  Parse the OCIO config file to get the location of the associated LUT files
def parse_ocio_config(config_file):

    def bunk_constructor(loader, node):
        pass

    yaml.add_constructor(u"ColorSpace", bunk_constructor)
    yaml.add_constructor(u"View", bunk_constructor)

    with open(config_file, 'r') as f:
        contents = yaml.load(f)

    config_path = os.path.dirname(config_file)
    print("Adding LUT config path %s" % config_path + "/" + contents['search_path'])
    return config_path + "/" + contents['search_path']

