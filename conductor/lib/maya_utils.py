import logging
import os
import re
import yaml
import functools
from maya import cmds, mel

from conductor.lib import package_utils, file_utils, xgen_utils
logger = logging.getLogger(__name__)


def dec_undo(func):
    '''
    DECORATOR - Wrap the decorated function in a Maya undo block.
    This is useful when wrapping functions which execute multiple maya commands,
    thereby altering maya's state and undo stack with multiple operations.
    This allows the artist to simply execute one undo call to undo all of the
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
    e.g. "Autodesk Maya 2015 SP4"
    '''
    return cmds.about(installedVersion=True)


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


def save_current_maya_scene():
    '''
    Saves current Maya scene using standard save command
    '''
    logger.debug("Saving Maya scene...")
    cmds.SaveScene()


def get_maya_save_state():
    '''
    Returns True if the current Maya scene has unsaved changes
    '''
    save_state = cmds.file(q=True, modified=True)
    return save_state


def get_maya_scene_filepath():
    filepath = cmds.file(q=True, sceneName=True)
    if not filepath or not os.path.isfile(filepath):
        raise Exception("Maya scene has not been saved to a file location.  Please save file before submitting to Conductor.")
    return str(filepath)


def get_image_dirpath():
    '''
    TODO: (lws)  Need to break up the logic on a per-plugin/renderer basis.

    This is high level function that "figures out"  the proper "output directory"
    for the conductor job being submitted.  As of now, the output directory is
    used for two separate purposes (which desperately need to be separated at some point).

    1. Dictates the directory to search for rendered images on ther render node
       when the render task completes.  If the rendered images cannot be found
       recursively within the given output path then the images will not get
       transferred to gcs, and therefore the task will have no frames to download.

    2. Dictates the default directory that the client downloader will download
       the task's frames to.  Note that the client downloader can manually override
       the download directory when evoking the downloader command manually
       (as opposed to running it in daemon mode).


    On a simple level, the output directory should be the directory in which
    maya renders its images to. However, this is directory is not straight forward process to derive.
    For starters, the "output directory" is not necessarily flat; it may contain
    nested directories (such as for render layers, etc) that were created by the
    rendering process. This is not actually a problem, but something to consider.
    Those nested directories will be represented/recreated when the resulting
    images are downloaded by the client.  But the important piece to note is that
    the output directory should be the "lowest" (longest) directory possible,
    while encompassing all rendered images from that task.

    The other part of the complexity, is that there are multiple places in maya
    to dictate where the "output directory" is (and I can't pretend to know every
    possible way of achieving this). As of now, these are the known factors:

    1. The Workspace's "image" directory is the default location for renders.
       (I'm not sure if this is even true).

    2. However, this can be essentially overridden within the global render
       settings if one were to populate "File Name Prefix" field with an
       absolute path. (perhaps there's another way to override the output directory
       but this is what I've observed thus far).

    3. Each renderer (such as vray or maya software) has a different node/attribute
       to set the File Name Prefix field.  So it's important to know which
       renderer is active in order to query the proper node for its data.
       As other renderersare added/supported by conductor, those nodes will need
       to be considered when querying for data.

     '''

    # Renderman is pretty straight forward. We'll simply provide the Renderman's image directory
    if is_renderman_renderer():
        return mel.eval('rmanGetImageDir')

    output_dirpath = get_workspace_image_dirpath()
    file_prefix = get_render_file_prefix()

    # If the file prefix is an absolute path, then use it's directory
    if file_prefix.startswith(os.sep):
        output_dirpath = derive_prefix_directory(file_prefix)

    return output_dirpath


def get_active_renderer():
    '''
    Return the name of the active renderer, e.g "vray" or "arnold
    '''
    return cmds.getAttr("defaultRenderGlobals.currentRenderer") or ""


def get_renderer_info(renderer_name=None):
    '''
    renderer_name: str. e.g. "vray" or "arnold"

    {"renderer_name": "vray",
     "plugin_name": "vrayformaya",
     "plugin_version": 3.00.01'}

    '''
    if not renderer_name:
        renderer_name = get_active_renderer()

    renderer_info = {"renderer_name": renderer_name}

    # Get the plugin name for the given renderer name
    plugin_name = get_renderer_plugin(renderer_name)
    if not plugin_name:
        raise Exception("Could not determine plugin from renderer: %s" % renderer_name)
    if not cmds.pluginInfo(plugin_name, q=True, loaded=True):
        cmds.loadPlugin(plugin_name)

    renderer_info["plugin_name"] = plugin_name
    renderer_info["plugin_version"] = cmds.pluginInfo(plugin_name, version=True, q=True)
    return renderer_info


def get_renderer_plugin(renderer_name):
    '''
    For the given renderer name, return the renderer's plugin name

    Attempt to find the corellation between the renderer name and the plugin name
    by asking maya for it's active renderer's global render settings node,
    and then asking what node type that is, and then asking which plugin provides
    the node type.

    # THIS DOESN'T ALWAYS WORK! For some reason the "vraysettings" node isn't
    # always listed as one of the global render settings nodes.  So we resort
    # to a hard mapping of needed
    '''
    # Mapping of render name to plugin name
    renderer_plugin_map = {"vray": "vrayformaya",
                           "arnold": "mtoa"}

    # register the rendeder if not's not already registered
    if not cmds.renderer(renderer_name, exists=True):
        logger.debug("registering renderer: %s", renderer_name)
        cmds.renderer(renderer_name)

    # Get all plugin node types
    plugin_node_types = {}
    for plugin_name in cmds.pluginInfo(q=True, listPlugins=True) or []:
        plugin_node_types[plugin_name] = cmds.pluginInfo(plugin_name, q=True, dependNode=True) or []

    # Cycle through all  all of the global render settings nodes
    for node in cmds.renderer(renderer_name, q=True, globalsNodes=True) or []:
        for plugin_name, node_types in plugin_node_types.iteritems():
            if cmds.nodeType(node) in node_types:
                return plugin_name

    # Resort to a hard-coded mapping as a fail-safe
    # TODO:(lws) This should not be necesary. Find a more reliable way to find the renderer plugin name!
    logger.warning("Unable to determine plugin from renderer's global render nodes. Resorting to hard mapping")
    return renderer_plugin_map.get(renderer_name)


def get_renderer_globals_node(renderer_name):
    '''
    For the given renderer name, return the name of its renderer globals node.

    #TODO:(lws)
    Note that if more than one node is found, raise an exception.  This is to
    simplify things for now, but may need to support multiple nodes later.

    renderer_name: str. e.g. "vray" or "arnold"

    return: str. e.g. "defaultRenderGlobals"
    '''
    if not renderer_exists(renderer_name):
        logger.debug("Renderer does not exist: %s", renderer_name)
        return ""

    globals_nodes = cmds.renderer(renderer_name, q=True, globalsNodes=True) or []
    if not globals_nodes:
        return ""

    if len(globals_nodes) > 1:
        raise Exception("More than 1 %s renderer globals node found: %s" % (renderer_name, globals_nodes))

    return globals_nodes[0]


def renderer_exists(renderer_name):
    '''
    Return True if the given renderer (name) can be found in the maya session

    renderer_name: str. e.g. "vray" or "arnold"
    '''
    return renderer_name in (cmds.renderer(q=True, namesOfAvailableRenderers=True) or [])


def get_render_file_prefix():
    '''
    Return the "File Name Prefix" from the global render settings. Note that this
    is a read from different node/attribute depending on which renderer is
    currently active.

    Note that as more renderers are supported by Conductor, this function may
    need to be updated to properly query those renderers' information.
    '''

    # Use the render globals node/attr by default
    prefix_node_attr = "defaultRenderGlobals.imageFilePrefix"

    # If the active renderer is vray, then use the vray node for the file prefix
    if is_vray_renderer():
        prefix_node_attr = "vraySettings.fileNamePrefix"

    # If the node doesn't exist, log an error. We could raise this as an exception,
    # but I'd rather not break the client
    if not cmds.objExists(prefix_node_attr):
        logger.error("Could not find expected node/attr: %s", prefix_node_attr)
        return ""

    return cmds.getAttr(prefix_node_attr) or ""


def derive_prefix_directory(file_prefix):
    '''
    This is a super hack that makes many assumptions.  It's purpose is to determine
    the top level render output directory.  Normally one could query the workspace's
    "images" directory to get this information, but in cases where the render
    file prefix specifies an absolute path(thereby overriding the workspace's
    specified directory), we must honor that prefix path.  The problem is that
    prefix path can contain variables, such as <Scene> or <RenderLayer>, which
    could be specific to whichever render layer is currently being rendered. So
    we need to navigate to highest common directory across all render layers.

    So if this is the prefix:
        "/shot_105/v076/<Layer>/105_light_<RenderLayer>_v076"
    ...then this is directory we want to return:
        "/shot_105/v076"

    However, there may not be *any* variables used. So if this is the prefix:
        "/shot_105/v076/105_light_v076"
    ...then this is directory we want to return (same as before):
        "/shot_105/v076"

    Note that the provided file_prefix is expected to be absolute path

    variables are such as:
        <Scene>
        <RenderLayer>
        <Camera>
        <RenderPassFileGroup>
        <RenderPass>
        <RenderPassType>
        <Extension>
        <Version>
        <Layer>

    '''
    assert file_prefix.startswith(os.sep), 'File Prefix expected to begin with "%s". file_prefix: %s' % (os.sep, file_prefix)
    rx = r"<\w+>"
    # If the the file prefix doesn't contain any variables, then simply return
    # the prefix's directory
    if not re.findall(rx, file_prefix):
        return os.path.dirname(file_prefix)

    prefix_reconstruct = ""
    for dir_token in file_prefix.split(os.sep)[1:]:
        if re.findall(rx, prefix_reconstruct):
            break
        prefix_reconstruct += os.sep + dir_token

    return os.path.dirname(prefix_reconstruct)


def get_maya_image_dirpath():
    '''
    Return the "images" directory for the active maya workspace
    '''
    image_filepath = cmds.renderSettings(fullPath=True, genericFrameImageName=True)
    assert len(image_filepath) == 1, image_filepath
    return os.path.dirname(image_filepath[0])


def get_workspace_image_dirpath():
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
    a a render layer.  Each dictionary provides the following information:
        - render layer name
        - whether the render layer is set to renderable
        - the camera that the render layer uses

    Note that only one camera is allowed per render layer.  This is somewhat
    of an arbitrary limitation, but implemented to reduce complexity.  This
    restriction may need to be removed.

    Note that this function is wrapped in an undo block because it actually changes
    the state of the maya session (unfortunately). There doesn't appear to be
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
        except RuntimeError:
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
    logger.debug("maya scene base dependencies: %s", dependencies)

    all_node_types = cmds.allNodeTypes()

    for node_type, node_attrs in node_attrs.iteritems():
        if node_type not in all_node_types:
            logger.debug("skipping unknown node type: %s", node_type)
            continue

        for node in cmds.ls(type=node_type):
            for node_attr in node_attrs:
                plug_name = '%s.%s' % (node, node_attr)
                if cmds.objExists(plug_name):
                    plug_value = cmds.getAttr(plug_name)
                    # Note that this command will often times return filepaths with an ending "/" on it for some reason. Strip this out at the end of the function
                    path = cmds.file(plug_value, expandName=True, query=True, withoutCopyNumber=True)
                    logger.debug("%s: %s", plug_name, path)

                    # ---- VRAY SCRAPING -----
                    if node_type == "VRayScene":
                        vrscene_dependencies = parse_vrscene_file(path)
                        logger.debug("vrscene dependencies: %s" % vrscene_dependencies)
                        dependencies += vrscene_dependencies

                    # ---- YETI SCRAPING -----
                    if node_type == "pgYetiMaya":
                        yeti_dependencies = scrape_yeti_graph(node)
                        logger.debug("yeti dependencies: %s" % yeti_dependencies)
                        dependencies += yeti_dependencies

                        # Check whether the node is reading from disk or not.
                        # If it's not, then we shouldn't include the path as
                        # a dependency
                        if not cmds.getAttr('%s.fileMode' % node):
                            logger.debug("Skipping path because fileMode is disabled")
                            continue

                    dependencies.append(path)

    # ---- workspace file ----
    workspace_dirpath = cmds.workspace(q=True, rootDirectory=True)
    workspace_filepath = os.path.join(workspace_dirpath, "workspace.mel")
    logging.debug(workspace_filepath)
    if os.path.isfile(workspace_filepath):
        dependencies.append(workspace_filepath)

    # ---- XGEN SCRAPING -----

    xgen_paths = xgen_utils.scrape_xgen()
    logger.debug("xgen_dependencies: %s", xgen_paths)
    dependencies += xgen_paths

    #  Grab any OCIO settings that might be there...
    ocio_config_filepath = get_ocio_config()
    if ocio_config_filepath:
        logger.info("OCIO config detected -- %s" % ocio_config_filepath)
        logger.debug("OCIO file: %s", ocio_config_filepath)
        dependencies.append(ocio_config_filepath)
        ocio_config_dependencies = parse_ocio_config(ocio_config_filepath)
        logger.debug("OCIO config dependencies: %s", ocio_config_dependencies)
        dependencies.append(ocio_config_dependencies)

    # Strip out any paths that end in "\"  or "/"    Hopefull this doesn't break anything.
    return sorted(set([path.rstrip("/\\") for path in dependencies]))


def get_ocio_config():
    plug_name = "defaultColorMgtGlobals.cfp"
    if cmds.objExists(plug_name):
        return cmds.getAttr(plug_name)


def scrape_yeti_graph(yeti_node):
    '''
    For the given pgYetiMaya node, scrape all of it's external file dependencies.

    Note that this node not only contains typical string attributes which may
    contain filepaths, but it also is a "gateway" into yeti's own internal dependency
    node system.... which must be queried for file dependencies as well.

    To further complicate things, these nodes allow paths to be defined relatively
    (rather than absolute), so we'll need to resolve them by reading the imageSearchPath
    attribute on the yeti node. TODO(lws): we may need to also include the
    PG_IMAGE_PATH environment variable as another search location.

    '''
    # If the node is reading from a cache file/directory, then ensure that it
    # exists on disk before attempting to read/traverse it's data
    if cmds.getAttr('%s.fileMode' % yeti_node):
        path = cmds.getAttr("%s.cacheFileName" % yeti_node)
        # if no path is specified, or the path doesn't resolves to any files, raise an exception
        if not path or not file_utils.process_upload_filepath(path):
            raise Exception("Cannot scrape yeti dependencies! Cache path does not exist: %s" % path)

    filepaths = []

    yeti_input_nodes = ["texture", "reference"]
    attr_name = "file_name"

    # Query the the yeti search paths from imageSearchPath attr.  This attr
    # will be a single string value that may contain multiple paths (just
    # like a typical environment variable might).
    search_paths = [p.strip() for p in (cmds.getAttr("%s.imageSearchPath" % yeti_node) or "").split(os.pathsep)]
    logger.debug("Yeti image search paths: %s", search_paths)

    for node_type in yeti_input_nodes:
        logger.debug("Traversing yeti %s nodes", node_type)
        for node in cmds.pgYetiGraph(yeti_node, listNodes=True, type=node_type) or []:

            filepath = cmds.pgYetiGraph(yeti_node,
                                        node=node,
                                        getParamValue=True,
                                        param=attr_name)
            logger.debug("Yeti graph node: %s.%s: %s", node, attr_name, filepath)
            if filepath:
                # if the filepath is absolute, then great; record it.
                if os.path.isabs(filepath):
                    filepaths.append(filepath)
                    continue

                # If the path is relative then we must construct a potential path
                # from each of our search paths, and check whether the path existst.
                logging.debug("Resolving relative path: %s", filepath)
                for search_path in search_paths:
                    full_path = os.path.join(search_path, filepath)
                    logging.debug("Checking for potential filepath: %s", full_path)
                    # We must account for cases where the path could actually
                    # be an expression (e.g. <udim>, etc), so we can't just check
                    # for the path's literal existence. Instead, we check whether
                    # the expression resolves in at least one path.  If it does
                    # then great; we've resolved our relative path.
                    if file_utils.process_upload_filepath(full_path, strict=False):
                        logging.debug("Resolved filepath: %s", full_path)
                        filepaths.append(full_path)
                        break
                else:
                    raise Exception("Couldn't resolve relative path: %s" % filepath)

    return filepaths


def parse_vrscene_file(path):
    '''
    Parse the vrscene file paths...
    '''
    files = []
    with open(path) as infile:
        for line in infile:
            res = re.findall('\s+file="(.+)"', line)
            if res:
                files += res
    return files


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

        m = re.match("\s+cacheFileName\s+(.+)", line)
        if m:
            file_path = m.group(1)
            file_paths.append(file_path)
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
                file_paths.append(os.path.join(project_dir, "xgen"))
                continue

    return file_paths

#  Parse the OCIO config file to get the location of the associated LUT files


def parse_ocio_config(config_file):

    def bunk_constructor(loader, node):
        pass

    yaml.add_constructor(u"ColorSpace", bunk_constructor)
    yaml.add_constructor(u"View", bunk_constructor)

    with open(config_file, 'r') as f:
        contents = yaml.safe_load(f)

    config_path = os.path.dirname(config_file)
    print("Adding LUT config path %s" % config_path + "/" + contents['search_path'])
    return config_path + "/" + contents['search_path']


def get_current_renderer():
    '''
    Return the name of the current renderer for the maya scene.
    e.g. 'vray' or 'arnold', etc
    '''
    return cmds.getAttr("defaultRenderGlobals.currentRenderer") or ""


def is_arnold_renderer():
    '''
    Return boolean to indicat whether arnold is the current renderer for the maya
    scene
    '''
    return get_current_renderer() in ["arnold"]


def is_vray_renderer():
    '''
    Return boolean to indicat whether vray is the current renderer for the maya
    scene
    '''
    return get_current_renderer() in ["vray"]


def is_renderman_renderer():
    '''
    Return boolean to indicat whether vray is the current renderer for the maya
    scene
    '''
    return get_current_renderer() in ["renderManRIS"]


def get_mayasoftware_settings_node(strict=True):
    '''
    Return the renderGlobals node in the maya scene.  If strict is True, and
    no node is found, raise an exception.
    '''
    node_type = "renderGlobals"
    default_name = "defaultRenderGlobals"
    mayasoftware_nodes = get_node_by_type(node_type, must_exist=strict, many=True)
    return _get_one_render_node(node_type, mayasoftware_nodes, default_name)


def get_vray_settings_node(strict=True):
    '''
    Return the VRaySettingsNode node in the maya scene.  If strict is True, and
    no node is found, raise an exception.
    '''
    node_type = "VRaySettingsNode"
    default_name = "vraySettings"
    vray_nodes = get_node_by_type(node_type, must_exist=strict, many=True)
    return _get_one_render_node(node_type, vray_nodes, default_name)


def get_arnold_settings_node(strict=True):
    '''
    Return the aiOptions node in the maya scene.  If strict is True, and
    no node is found, raise an exception.
    '''
    node_type = "aiOptions"
    default_name = "defaultArnoldRenderOptions"
    arnold_nodes = get_node_by_type(node_type, must_exist=strict, many=True)
    return _get_one_render_node(node_type, arnold_nodes, default_name)


def _get_one_render_node(node_type, render_settings_nodes, default_name):
    '''
    helper function to return one node of the given render_settings_nodes.

    If more than on node exists, use the one that has the default name. Otherwise
    throw an exception. This is really just a temporary hack until we can figure
    out (decisively via an api call) as to which node is the active render node
    for the maya scene.
    '''
    if not render_settings_nodes:
        return ""

    if len(render_settings_nodes) > 1:
        if default_name not in render_settings_nodes:
            raise Exception("Multiple %s nodes found in maya scene: %s" %
                            (node_type, render_settings_nodes))
        return default_name

    return render_settings_nodes[0]


def get_render_settings_node(renderer_name, strict=True):
    '''
    return the name of the renderer's settings node.
    e.g. "defaultRenderGlobals" or "vraySettings" or "defaultArnoldRenderOptions"
    '''
    renderer_settings_gettr = {"vray": get_vray_settings_node,
                               "arnold": get_arnold_settings_node,
                               "mayaSoftware": get_mayasoftware_settings_node}

    if renderer_name not in renderer_settings_gettr and strict:
        raise Exception("Renderer not supported: %s", renderer_name)

    return renderer_settings_gettr[renderer_name](strict=strict)


def is_vray_gpu_enabled():
    '''
    Return True if a GPU mode is selected in V-Ray's render settings
    Current potential values set on V-Ray's productionEngine attr are:
    0 = CPU mode (False)
    1 = OpenCL mode (False - not supported on Intel/NVIDIA hardware)
    2 = CUDA mode (True)
    '''
    vray_node = get_vray_settings_node(strict=False)
    if vray_node:
        production_engine = cmds.getAttr("%s.productionEngine" % vray_node)
        return production_engine == 2
    return False


def is_arnold_tx_enabled():
    '''
    Return True if the "Use Existing .tx Textures" option is enabled in Arnolds
    render settings
    '''
    arnold_node = get_arnold_settings_node(strict=False)
    if arnold_node:
        return cmds.getAttr("%s.use_existing_tiled_textures" % arnold_node)


def get_node_by_type(node_type, must_exist=True, many=False):
    '''
    For the given node type, return the one node found in the maya scene of that
    type. If many is True, allow more than one to be returned, otherwise raise
    an exception if more than one is found. If must_exist is True, raise an
    exception if no nodes are found in the maya scene.
    '''

    nodes = cmds.ls(type=node_type) or []
    if not nodes and must_exist:
        raise Exception("No %s nodes found in maya scene." % node_type)

    if (len(nodes) > 1) and not many:
        raise Exception("More than one %s node found in maya scene: %s" % (node_type, nodes))

    # If many are allowed, return a list of all nodes (possibly empty list)
    if many:
        return nodes

    # Otherwise return a single value

    # if there is a value in the list, then return it
    if nodes:
        return nodes[0]

    # Otherwise return an empty string
    return ""

# def get_plugins_info():
#     plugins_info = []
#     for PluginClass in PLUGIN_CLASSES:
#         if PluginClass.exists():
#             plugins_info.append(PluginClass.get())
#     return plugins_info


def get_plugin_info():
    '''
    Return the conductor package information for any supported plugins
    that are loaded.

     e.g.
        {'arnold-maya': u'1.4.2.1',
         'miarmy': u'5.2.25',
         'v-ray-maya': u'3.40.02'}
    '''
    plugins_info = {}
    for PluginClass in PLUGIN_CLASSES:
        if PluginClass.exists():
            plugins_info[PluginClass.get_product()] = PluginClass.get_version()
    return plugins_info


def get_plugin_info_class(plugin_name):
    for PluginClass in PLUGIN_CLASSES:
        if plugin_name == PluginClass.plugin_name:
            return PluginClass


class MayaInfo(package_utils.ProductInfo):
    '''
    A class for retrieving version information about the current maya session.

    Will ultimately produce something like this
     # This is package for Maya
      {'product': 'Maya'
       'version': "Autodesk Maya 2015 SP4"
       'host_product': '',
       'host_version': ''},

    '''
    product = "maya"

    @classmethod
    def get_product(cls):
        '''
        Return the name of the product, e.g.

            "Maya"
        '''
        return cls.product

    @classmethod
    def get_version(cls):
        '''
        Return the product verion, e.g.

            "Autodesk Maya 2015 SP4"
        '''
        return cmds.about(installedVersion=True)

    @classmethod
    def get_major_version(cls):
        '''
        Return the major version of the product, e.g.

            "2015"
        '''
        return cls.regex_version().get("major_version", "")

    @classmethod
    def get_minor_version(cls):
        '''
        Return the minor version of the product, e.g.

            "SP4"
        '''
        return cls.regex_version().get("minor_version", "")

    @classmethod
    def get_vendor(cls):
        return "Autodesk"

    @classmethod
    def get_regex(cls):
        '''
        Regex the Maya product version string

        Autodesk Maya 2014 x64 Service Pack 1
        Autodesk Maya 2014 Service Pack 2
        Autodesk Maya 2014 Service Pack 3
        Autodesk Maya 2015 SP1
        Autodesk Maya 2015 SP4
        Autodesk Maya 2016 SP4
        Autodesk Maya 2016 Extension 1 + SP5
        '''
        rx_prefix = 'Autodesk Maya'
        rx_major = r'(?P<major_version>\d+)'
        rx_minor = r'(?P<minor_version>SP\d+)?'  # optionally get the service pack
        rx = r'{} {} {}'.format(rx_prefix, rx_major, rx_minor)
        return rx


class MayaPluginInfo(package_utils.ProductInfo):
    '''
    A class for retrieving version information about a plugin in maya

    Will ultimately produce something like this

     {'product': '<plugin name>',
      'major_version': u'3',
      'minor_version': u'00',
      'release_version': u'01',
      'build_version': '',
      'plugin_host_product': 'maya',
      'plugin_host_version': u'2015'}
    '''

    plugin_name = None

    @classmethod
    def get_product(cls):
        raise NotImplementedError

    @classmethod
    def get_plugin_host_product(cls):
        '''
        Return the name of the host software package, e.g. "Maya" or "Katana"
        '''
        return MayaInfo.get_product()

    @classmethod
    def get_plugin_host_version(cls):
        '''
        Return the name of the host software package, e.g. "Autodesk Maya 2015 SP4"
        '''
        return MayaInfo.get_major_version()

    @classmethod
    def get_version(cls):
        return cmds.pluginInfo(cls.plugin_name, version=True, q=True) or ""

    @classmethod
    def exists(cls):
        return cmds.pluginInfo(cls.plugin_name, loaded=True, q=True)

    @classmethod
    def get_regex(cls):
        raise NotImplementedError


class VrayInfo(MayaPluginInfo):
    '''
    A class for retrieving version information about the vray plugin in maya

    Will ultimately produce something like this

     {'product': 'vrayformaya',
      'major_version': u'3',
      'minor_version': u'00',
      'release_version': u'01',
      'build_version': '',
      'plugin_host_product': 'maya',
      'plugin_host_version': u'2015'}
    '''
    plugin_name = "vrayformaya"

    @classmethod
    def get_product(cls):
        return "v-ray-maya"

    @classmethod
    def get_regex(cls):
        '''
        3.00.01
        '''
        rx_major = r'(?P<major_version>\d+)'
        rx_minor = r'(?P<minor_version>\d+)'
        rx_release = r'(?P<release_version>\d+)'
        rx = r'{}\.{}\.{}'.format(rx_major, rx_minor, rx_release)
        return rx


class ArnoldInfo(MayaPluginInfo):
    '''
    A class for retrieving version information about the arnold plugin in maya

    Will ultimately produce something like this

     {'product': 'mtoa',
      'major_version': u'1',
      'minor_version': u'2',
      'release_version': u'6',
      'build_version': u'1',
      'plugin_host_product': 'maya',
      'plugin_host_version': u'2015'}

    '''
    plugin_name = "mtoa"

    @classmethod
    def get_product(cls):
        return "arnold-maya"

    @classmethod
    def get_regex(cls):
        '''
        '1.2.6.1'
        '''
        rx_major = r'(?P<major_version>\d+)'
        rx_minor = r'(?P<minor_version>\d+)'
        rx_release = r'(?P<release_version>\d+)'
        rx_build = r'(?P<build_version>\d+)'
        rx = r'{}\.{}\.{}\.{}'.format(rx_major, rx_minor, rx_release, rx_build)
        return rx


class RendermanInfo(MayaPluginInfo):
    '''
    A class for retrieving version information about the renderman plugin in maya

    Will ultimately produce something like this

     {'product': 'mtoa',
      'major_version': u'1',
      'minor_version': u'2',
      'release_version': u'6',
      'build_version': u'1',
      'plugin_host_product': 'maya',
      'plugin_host_version': u'2015'}

    '''
    plugin_name = "RenderMan_for_Maya"

    @classmethod
    def get_product(cls):
        return "renderman-maya"

    @classmethod
    def get_regex(cls):
        '''
        '21.5'
        '''
        rx_major = r'(?P<major_version>\d+)'
        rx_minor = r'(?P<minor_version>\d+)'
        rx = r'{}\.{}'.format(rx_major, rx_minor)
        return rx


class MiarmyBaseInfo(MayaPluginInfo):
    '''
    Base class for all Miarmy plugins.  This base class DOES NOT
    represent any one miarmy plugin. It must be subclassed.

    A class for retrieving version information about the Miarmy plugin in maya

    Will ultimately produce something like this

     {'product': 'miarmy',
      'major_version': u'5',
      'minor_version': u'2',
      'release_version': u'25',
      'build_version': u'',
      'plugin_host_product': 'maya',
      'plugin_host_version': u'2016'}

    '''

    @classmethod
    def get_product(cls):
        return "miarmy"

    @classmethod
    def get_regex(cls):
        '''
        '1.2.6'
        '''
        rx_major = r'(?P<major_version>\d+)'
        rx_minor = r'(?P<minor_version>\d+)'
        rx_release = r'(?P<release_version>\d+)'
        rx = r'{}\.{}\.{}'.format(rx_major, rx_minor, rx_release)
        return rx


class MiarmyExpressForMaya2016Info(MiarmyBaseInfo):
    plugin_name = "MiarmyExpressForMaya2016"


class MiarmyExpressForMaya20165Info(MiarmyBaseInfo):
    plugin_name = "MiarmyExpressForMaya20165"


class MiarmyExpressForMaya2017Info(MiarmyBaseInfo):
    plugin_name = "MiarmyExpressForMaya2017"


class MiarmyProForMaya2016Info(MiarmyBaseInfo):
    plugin_name = "MiarmyProForMaya2016"


class MiarmyProForMaya20165Info(MiarmyBaseInfo):
    plugin_name = "MiarmyProForMaya20165"


class MiarmyProForMaya2017Info(MiarmyBaseInfo):
    plugin_name = "MiarmyProForMaya2017"


class YetiInfo(MayaPluginInfo):
    '''
    A class for retrieving version information about the yeti plugin in maya

    Will ultimately produce something like this

     {"product": "yeti",
      "major_version": "2",
      "minor_version": "1",
      "release_version": "9",
      "build_version": "",
      "plugin_host_product": "maya",
      "plugin_host_version": "2016"}
    '''
    plugin_name = "pgYetiMaya"

    @classmethod
    def get_product(cls):
        return "yeti"

    @classmethod
    def get_regex(cls):
        '''
        2.1.9
        '''
        rx_major = r'(?P<major_version>\d+)'
        rx_minor = r'(?P<minor_version>\d+)'
        rx_release = r'(?P<release_version>\d+)'
        rx = r'{}\.{}\.{}'.format(rx_major, rx_minor, rx_release)
        return rx

PLUGIN_CLASSES = [
    ArnoldInfo,
    MiarmyExpressForMaya2016Info,
    MiarmyExpressForMaya20165Info,
    MiarmyExpressForMaya2017Info,
    MiarmyProForMaya2016Info,
    MiarmyProForMaya20165Info,
    MiarmyProForMaya2017Info,
    RendermanInfo,
    VrayInfo,
    YetiInfo,
]
