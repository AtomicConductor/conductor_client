# Standard libs
import collections
import functools
import logging
import os
import re
import shlex
import tempfile

# Maya libs
from maya import cmds, mel

# Conductor libs
from conductor.lib import common, package_utils, file_utils

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
       As other renderers are added/supported by conductor, those nodes will need
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


def get_workspace_dirpath():
    '''
    Return the current Workspace directory
    '''
    return cmds.workspace(q=True, rootDirectory=True)


def get_workspace_image_dirpath():
    '''
    Return the current workspace's image directory
    '''
    workspace_root = get_workspace_dirpath()
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
        - the cameras that the render layer is set to render

    Note that this function is wrapped in an undo block because it actually changes
    the state of the maya session (unfortunately). There doesn't appear to be
    an available api call to query maya for this information, without changing
    it's state (switching the active render layer)
    '''
    render_layers = []

    # record the original render layer so that we can set it back later. Wow this sucks
    original_render_layer = cmds.editRenderLayerGlobals(currentRenderLayer=True, q=True)
    for render_layer in cmds.ls(type="renderLayer"):
        layer_info = {"layer_name": render_layer}
        try:
            cmds.editRenderLayerGlobals(currentRenderLayer=render_layer)
        except RuntimeError:
            continue

        cameras = []
        # cycle through all renderable camereras in the maya scene
        for camera in cmds.ls(type="camera", long=True):
            if not cmds.getAttr("%s.renderable" % camera):
                continue
            camera_info = {}
            camera_info["camera_transform"] = get_transform(camera)
            camera_info["camera_shortname"] = get_short_name(camera_info["camera_transform"])
            cameras.append(camera_info)

        layer_info["cameras"] = cameras
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

    # collect a list of ass filepaths that we can process at one time at the end of function, rather
    # than on a per node/attr basis (much slower)
    ass_filepaths = []

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
                    # Skip any empty values
                    if not plug_value:
                        continue

                    # Note that this command will often times return filepaths with an ending "/" on it for some reason. Strip this out at the end of the function
                    path = cmds.file(plug_value, expandName=True, query=True, withoutCopyNumber=True)
                    logger.debug("%s: %s", plug_name, path)

                    # ---- XGEN SCRAPING -----
                    #  For xgen files, read the .xgen file and parse out the directory where other dependencies may exist
                    if node_type == "xgmPalette":
                        maya_filepath = cmds.file(query=True, sceneName=True)
                        palette_filepath = os.path.join(os.path.dirname(maya_filepath), plug_value)
                        xgen_dependencies = scrape_palette_node(node, palette_filepath)
                        logger.debug("xgen_dependencies: %s", xgen_dependencies)
                        dependencies += xgen_dependencies

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

                    # ---- ARNOLD STANDIN SCRAPING -----
                    if node_type == "aiStandIn":
                        # We expect an aiStandin node to point towards and .ass file (or sequence thereof)
                        # Instead of loading/reading the .ass file now, simply append to a list
                        # that we'll process all at one time (*much faster*)

                        # The ass_filepath may actually be an expression (of several ass filepaths). Resolve the path
                        # to at least one file, and only scrape that one file.  The assumption here is that every .ass
                        # file in an .ass sequence will have the same file dependencies, so don't bother reading every
                        # ass file. Perhaps dangerous, but we'll cross that bridge later (it's better than reading/loading
                        # potentially thousands of .ass files)
                        ass_filepath = file_utils.process_upload_filepath(path, strict=True)[0]
                        ass_filepaths.append(ass_filepath)

                    # ---- RENDERMAN RLF files -----
                    # If the node type is a RenderManArchive, then it may have an associated .rlf
                    # file on disk. Unfortunatey there doesn't appear to a direct reference to that
                    # path anywhere, so we'll have to rely upon convention, where a given rib
                    # archive, such as
                    #     renderman/ribarchives/SpidermanRibArchiveShape.zip
                    # will have it's corresponding .rlf file here:
                    #     renderman/ribarchives/SpidermanRibArchiveShape/SpidermanRibArchiveShape.job.rlf
                    if node_type == "RenderManArchive" and node_attr == "filename":
                        archive_dependencies = []
                        rlf_dirpath = os.path.splitext(path)[0]
                        rlf_filename = "%s.job.rlf" % os.path.basename(rlf_dirpath)
                        rlf_filepath = os.path.join(rlf_dirpath, rlf_filename)
                        logger.debug("Searching for corresponding rlf file: %s", rlf_filepath)
                        rlf_filepaths = file_utils.process_upload_filepath(rlf_filepath, strict=False)
                        if rlf_filepaths:
                            rlf_filepath = rlf_filepaths[0]  # there should only be one
                            # Parse the rlf file for file dependencies.
                            # Note that though this is an rlf file, there is embedded rib data within
                            # that we can parse using this rib parser.
                            logger.debug("Parsing rlf file: %s", rlf_filepath)
                            rlf_depedencies = parse_rib_file(rlf_filepath)
                            archive_dependencies.extend([rlf_filepath] + rlf_depedencies)

                        logger.debug('%s dependencies: %s', plug_name, archive_dependencies)
                        dependencies.extend(archive_dependencies)

                    # Append path to list of dependencies
                    dependencies.append(path)

    # ---- OCIO SCRAPING -----
    ocio_dependencies = scrape_ocio_dependencies()
    logger.debug("ocio_dependencies: %s", ocio_dependencies)
    dependencies.extend(ocio_dependencies)

    # ---- ARNOLD .ASS SCRAPING -----
    # If any ass_filepaths were found, we need to process their dependencies as well.
    # Note that we intentionally maintain an explicit list of .ass files (rather than simply searching
    # through all of our dependencies thus far for a .ass extension) because there may some ass files
    # that are dependencies, but are not necessary (or redundant) to load/parse (i.e. in the case of
    # ass sequences.
    if ass_filepaths:
        resources = common.load_resources_file()
        ass_attrs = resources.get("arnold_dependency_attrs") or {}
        ass_dependencies = scrape_ass_files(ass_filepaths, ass_attrs)
        logger.debug("Arnold .ass_dependencies: %s" % ass_dependencies)
        dependencies.extend(ass_dependencies)

    # Strip out any paths that end in "\"  or "/"    Hopefully this doesn't break anything.
    return sorted(set([path.rstrip("/\\") for path in dependencies]))


def scrape_yeti_graph(yeti_node):
    '''
    For the given pgYetiMaya node, scrape all of it's external file dependencies.

    Note that this node not only contains typical string attributes which may
    contain filepaths, but it also is a "gateway" into yeti's own internal dependency
    node system.... which must be queried for file dependencies as well.

    To further complicate things, these nodes allow paths to be defined relative/global
    (rather than absolute), so we'll need to resolve them by reading the imageSearchPath
    attribute on the yeti node, as well as searching any search paths defined in PG_IMAGE_PATH
    environment variable.

    '''
    # If the node is reading from a cache file/directory, then ensure that it
    # exists on disk before attempting to read/traverse it's data
    if cmds.getAttr('%s.fileMode' % yeti_node):
        path = cmds.getAttr("%s.cacheFileName" % yeti_node)
        # if no path is specified, or the path doesn't resolves to any files, raise an exception
        if not path or not file_utils.process_upload_filepath(path):
            raise Exception("Cannot scrape yeti dependencies! Cache path does not exist: %s" % path)

    filepaths = []

    yeti_input_attrs = {
        "texture": ["file_name"],
        "reference": ["reference_file"]
    }

    # Query the the yeti search paths from imageSearchPath attr.  This attr
    # will be a single string value that may contain multiple paths (just
    # like a typical environment variable might).
    node_search_paths = [p.strip() for p in (cmds.getAttr("%s.imageSearchPath" % yeti_node) or "").split(os.pathsep)]
    logger.debug("%s image search paths: %s", yeti_node, node_search_paths)

    # Get any search paths defined by the PG_IMAGE_PATH env variable
    pg_image_search_paths = [p.strip() for p in os.environ.get("PG_IMAGE_PATH", "").split(os.pathsep)]
    logger.debug("PG_IMAGE_PATH search paths: %s", pg_image_search_paths)

    search_paths = node_search_paths + pg_image_search_paths
    logger.debug("combined image search paths: %s", search_paths)

    for node_type, attr_names in yeti_input_attrs.iteritems():
        logger.debug("Traversing yeti %s nodes", node_type)
        node_filepaths = scrape_yeti_node_type(yeti_node, node_type, attr_names, search_paths=node_search_paths)
        filepaths.extend(node_filepaths)
    return filepaths


def scrape_yeti_node_type(yeti_node, node_type, attr_names, search_paths=()):
    '''
    Scrape the given PgYetiMaya node for all yeti nodes of the given node_type.

    args
        yeti_node: str. The name of the PyYetiNode to scrape for dependencies.
        node_type: str. The name of yeti node type to scrape for dependencies.
        attr_names: list of str. The names of the yeti node's attributes to read for dependencies.
        search_paths: an optional list of directories to resolved any relative/global
        files that are found.

    return:
        A list of filepaths
    '''
    node_filepaths = []
    for attr_name in attr_names:
        for node in cmds.pgYetiGraph(yeti_node, listNodes=True, type=node_type) or []:

            filepath = cmds.pgYetiGraph(yeti_node,
                                        node=node,
                                        getParamValue=True,
                                        param=attr_name)

            logger.debug("Yeti graph node: %s.%s: %s", node, attr_name, filepath)
            if filepath:
                #  Yeti nodes may store the filepath in either forward slash or backslash format (ugh).
                # This is problematic if the content is initially created on one platform (like Windows)
                # but is now currently opened on a different platform (like linux), which doesn't acknowledge
                # backslashes as path separators (since a backslash is a valid character in unix path).
                # So we must choose between two evils and simply assume that all backslashes are intended
                # to be directory separators, and so we convert them to forward slashes (which Windows
                # will handle just fine as well).
                filepath = os.path.normpath(filepath).replace('\\', "/")
                logger.debug("Conformed path: %s", filepath)
                # if the filepath is absolute, then great; record it.
                if os.path.isabs(filepath):
                    node_filepaths.append(filepath)
                    continue

                # If the path is relative then we must construct a potential path
                # from each of our search paths, and check whether the path existst.
                logger.debug("Resolving relative path: %s", filepath)
                for search_path in search_paths:
                    full_path = os.path.join(search_path, filepath)
                    logger.debug("Checking for potential filepath: %s", full_path)
                    # We must account for cases where the path could actually
                    # be an expression (e.g. <udim>, etc), so we can't just check
                    # for the path's literal existence. Instead, we check whether
                    # the expression resolves in at least one path.  If it does
                    # then great; we've resolved our relative path.
                    resolved_filepaths = file_utils.process_upload_filepath(full_path, strict=False)
                    if resolved_filepaths:
                        logger.debug("Resolved filepaths: %s", resolved_filepaths)
                        node_filepaths.extend(resolved_filepaths)
                        break
                else:
                    raise Exception("Couldn't resolve relative path: %s" % filepath)

    return node_filepaths


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


def parse_rib_file(filepath):
    '''
    Parse the given rib filepath for file dependencies

    In leui of  python rib parser/api, we need need to resort to some awful hacks here.

    We use prman library to read the rib file.  The only benefit that this provides is that it can
    read a binary rib file and output it to ascii.  Aside from that, we're doing crude regex matching
    from the content (no api for interfacing with ribs :( ).

    Regex for attribites suchs as:
        filename
        fileTextureName
    '''

    # Make sure the renderman plugin is loaded so that we can use it's python lib
    try:
        if not cmds.pluginInfo(RendermanInfo.plugin_name, q=True, loaded=True):
            cmds.loadPlugin(RendermanInfo.plugin_name)
    except RuntimeError:
        logger.warning("Could not load %s plugin. Cannot parse rib/rlf file", RendermanInfo.plugin_name)
        return []
    try:
        import prman
    except ImportError:
        logger.warning('Failed to import prman module. Cannot parse rib/rlf file')
        return []

    # Unfortunately renderman api can't write to an object it memory that we can use, so we'll
    # need to make a tmpfile on disk to write to, and then read it back.
    tmpfile = tempfile.NamedTemporaryFile(prefix="tmp-conductor-")
    tmpfilepath = tmpfile.name
    tmpfile.close()

    # Use the renderman api to read the rib file, and write it back out to the temp file
    # the only purpose for doing so is so that we can read binary ribs.
    # Access prman's RiXXX procs and definitions
    ri = prman.Ri()
    # Format the output for easier reading;
    ri.Option("rib", {"string asciistyle": "indented"})
    ri.Begin(tmpfilepath)           # Echo the rib as it is processed;
    # Process the input rib. the function will fail if given a unicode string, so convert to regular string.
    prman.ParseFile(filepath.encode('utf8'))
    ri.End()

    # Read the rib from the tmpfile, and crudely parse for paths of interest.
    # I wish there was a rib api to allow access to elements/attributes in a rib file :(
    paths = []
    with open(tmpfilepath) as f:
        for line in f:
            match = re.search(r'string (?:filename|fileTextureName)" \["([^"]+)"\]', line)
            if match and match.group(1) not in ["stdout"]:
                paths.append(match.group(1))

    # Resolve any paths that are relative, unresolved, etc
    filepaths = []
    for path in paths:
        # If the path is relative, resolve it by joining with workspace root
        if not os.path.isabs(path):
            path = os.path.join(get_workspace_dirpath(), path)
        # process the path to resolve any other variables/characters/tokens, etc
        filepaths.extend(file_utils.process_upload_filepath(path, strict=False))

    # Delete the tmpfile
    os.remove(tmpfilepath)

    return filepaths


def scrape_ocio_dependencies():
    '''
    Find the ocio config file (if it exists) and scrape it for external file dependencies
    '''
    config_filepath = get_ocio_config_filepath()
    if config_filepath:
        return parse_ocio_config_paths(config_filepath)
    return []


def get_ocio_config_filepath():
    '''
    Return the OCIO config filepath from maya settings.

    Only return the filepath if color managment is enabled and OCIO config is enabled.
    '''
    if (cmds.colorManagementPrefs(q=True, cmEnabled=True) and

            cmds.colorManagementPrefs(q=True, cmConfigFileEnabled=True)):
        return cmds.colorManagementPrefs(q=True, configFilePath=True)


def parse_ocio_config_paths(config_filepath):
    '''
    Parse the given OCIO config file for any paths that we may be interested in (for uploads)

    For now, we'll keep this simple and simply scrape the "search_path" value in the config file.
    However, it's possible that additional attributes in the config will need to be queried.
    '''

    if not os.path.isfile(config_filepath):
        raise Exception("OCIO config file does not exist: %s" % config_filepath)

    paths = []

    search_path_str = _get_ocio_search_path(config_filepath)
    logger.warning("Could not find PyOpenColorIO library.  Resorting to basic yaml loading")
    config_dirpath = os.path.dirname(config_filepath)
    search_paths = search_path_str.split(os.pathsep)
    logger.debug("Resolving config seach paths: %s", search_paths)
    for path in search_paths:
        # If the path is relative, resolve it
        if not os.path.isabs(path):
            path = os.path.join(config_dirpath, path)
            logging.debug("Resolved relative path '%s' to '%s'", )

        if not os.path.isdir(path):
            logger.warning("OCIO search path does not exist: %s", path)
            continue
        logger.debug("adding directory: %s", path)
        paths.append(path)

    return paths + [config_filepath]


def _get_ocio_search_path(config_filepath):
    '''
    Get the "search_path" value in the config file.
    Though an OCIO config file is yaml, it may have custom data types (yaml tags) defined within it
    which can prevent a succesful reading when using a simple yaml.load call. So we try two
    different approaches for reading the file:
        1. Use OpenColorIO api.  This library/tools may not be available on a client's machine.
        2. Use pyyaml to load the yaml file and use a custom yaml constructor to omit the yaml tags
           from being read.
    '''
    logger.debug("Reading OCIO config from: %s", config_filepath)
    try:
        import PyOpenColorIO
    except ImportError as e:
        logger.warning(e)
        logger.warning("Could not find PyOpenColorIO library.  Loading OCIO config via yaml loader")
        config = common.load_yaml(config_filepath, safe=True, omit_tags=True)
        return config.get("search_path")
    else:
        config = PyOpenColorIO.Config.CreateFromFile(config_filepath)
        return config.getSearchPath()


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


def scrape_ass_files(ass_filepaths, node_attrs, plugin_paths=()):
    '''
    Read/load the given arnold files with the arnold api, and seek out nodes that have filepaths
    of interest.

    todo(lws): Still need to investigate why this crashes in mayapy when arnold plugins are
        present (such as yeti or alshaders).

    node_attrs: dictionary. key is the node type, value is a list of node attributes to query.

    plugin_paths: tuple of strings. This may be necessary when running outside of maya/interactive,
        so that nodes for arnold plugins (yeti, etc) can be properly loaded/used.

        e.g. ("/usr/anderslanglands/alshaders/alShaders-linux-2.0.0b2-ai5.0.1.0/bin",
              "/usr/peregrinelabs/yeti/Maya2017/Yeti-v2.2.6_Maya2017-linux64/bin")

    '''
    cmds.loadPlugin("mtoa")
    try:
        import arnold
    except ImportError:
        logger.warning("Failed to import arnold. Could not scrape arnold files: %s", ass_filepaths)
        return []

    arnold.AiBegin()
    try:
        arnold.AiMsgSetConsoleFlags(arnold.AI_LOG_ALL)
        if plugin_paths:
            arnold.AiLoadPlugins(os.path.sep.join(plugin_paths))
        paths = []
        for ass_filepath in ass_filepaths:
            logger.debug("Scraping Arnold file: %s", ass_filepath)
            deps = _scrape_ass_file(ass_filepath, node_attrs)
            paths.extend(deps)
    finally:
        arnold.AiEnd()

    return paths


def scrape_ass_file(ass_filepath, node_attrs, plugin_paths=()):
    '''
    Read/load the given arnold file with the arnold api, and seek out nodes that have filepaths
    of interest.

    todo(lws): Still need to investigate why this crashes in mayapy when arnold plugins are
        present (such as yeti or alshaders).

    node_attrs: dictionary. key is the node type, value is a list of node attributes to query.

    plugin_paths: tuple of strings. This may be necessary when running outside of maya/interactive,
        so that nodes for arnold plugins (yeti, etc) can be properly loaded/used.

        e.g. ("/usr/anderslanglands/alshaders/alShaders-linux-2.0.0b2-ai5.0.1.0/bin",
              "/usr/peregrinelabs/yeti/Maya2017/Yeti-v2.2.6_Maya2017-linux64/bin")
    '''
    cmds.loadPlugin("mtoa")
    try:
        import arnold
    except ImportError:
        logger.warning("Failed to import arnold. Could not scrape arnold file: %s", ass_filepath)
        return []

    arnold.AiBegin()
    arnold.AiMsgSetConsoleFlags(arnold.AI_LOG_ALL)
    if plugin_paths:
        arnold.AiLoadPlugins(os.path.sep.join(plugin_paths))

    paths = _scrape_ass_file(ass_filepath, node_attrs)
    arnold.AiEnd()
    return paths


def _scrape_ass_file(ass_filepath, node_attrs):
    '''
    Read/load the given arnold file with the arnold api, and query the given the node/attrs
    for paths of interest.

    node_attrs: dictionary. key is the node type, value is a list of node attributes to query.

    NOTE: this should not be called directly (requires some initialization/cleanup)
    '''

    import arnold

    paths = []
    arnold.AiASSLoad(ass_filepath, arnold.AI_NODE_ALL)

    # Iterate over all shape nodes, which includes procedural nodes
    iterator = arnold.AiUniverseGetNodeIterator(arnold.AI_NODE_ALL)
    while not arnold.AiNodeIteratorFinished(iterator):
        node = arnold.AiNodeIteratorGetNext(iterator)
        entryNode = arnold.AiNodeGetNodeEntry(node)
        node_type = arnold.AiNodeEntryGetName(entryNode)
        for attr_name in node_attrs.get(node_type) or []:
            value = arnold.AiNodeGetStr(node, attr_name)

            if node_type == "xgen_procedural":
                logger.debug("Parsing xgen_procedural..")
                xgen_paths = scrape_arnold_xgen_data_str(value)
                paths.extend(xgen_paths)

            elif value:
                paths.append(value)

    arnold.AiNodeIteratorDestroy(iterator)
    return paths


def scrape_arnold_xgen_data_str(string):
    '''
    Parse the given xgen_procedural.data string value into separate parts, and scrape each part
    for dependencies
    '''
    paths = set()

    # First convert the string of arg
    xgen_args = parse_xgen_command(string)
    for flag in ("file", 'geom'):
        logger.debug('Reading "%s" flag', flag)
        if flag not in xgen_args:
            logger.warning('"%s" flag not found in xgen procedural.  Skipping', flag)
            continue
        path = xgen_args[flag]
        logger.debug("path: %s", path)
        if not path:
            logger.warning('"%s" does not have a path specified', flag)
            continue
        paths.add(path)

    # Parse xgen file dependencies
    xgen_dependencies = set()
    for path in paths:
        if path.lower().endswith(".xgen"):
            logger.debug("scraping dependencies for xgen file: %s", path)
            if not os.path.isfile(path):
                logger.warning("File does not exist, skipping: %s", path)
                continue
            xgen_dependencies.update(scrape_xgen_file(path))

    return list(paths | xgen_dependencies)


def parse_xgen_command(cmd_str):
    '''
    Parse xgen produceral command/args. Very crude with many assumptions.

    args:
        cmd_str: str. The string to parse, e.g.
        '-debug 1 -warning 1 -stats 1  -frame 1.000000  -nameSpace cat_main -file /tmp/cat.xgen -palette cat_xgen_coll -geom /tmp/cat_xgen_coll.abc -patch Paw_R_emitter -description catcuff_xgen_desc -fps 24.000000  -motionSamplesLookup -0.250000 0.250000  -motionSamplesPlacement -0.250000 0.250000  -world 1;0;0;0;0;1;0;0;0;0;1;0;0;0;0;1'

    return: dict:, e.g.
        {'debug': '1',
         'description': 'catcuff_xgen_desc',
         'file': '/tmp/cat.xgen',
         'fps': '24.000000',
         'frame': '1.000000',
         'geom': '/tmp/cat_xgen_coll.abc',
         'motionSamplesLookup': ['-0.250000', '0.250000'],
         'motionSamplesPlacement': ['-0.250000', '0.250000'],
         'nameSpace': 'cat_main',
         'palette': 'cat_xgen_coll',
         'patch': 'Paw_R_emitter',
         'stats': '1',
         'warning': '1',
         'world': '1;0;0;0;0;1;0;0;0;0;1;0;0;0;0;1'}

    '''
    args = collections.defaultdict(list)
    attr = None
    for part in shlex.split(cmd_str):
        if part.startswith("-") and not _is_number(part):
            attr = part.lstrip("-")
        else:
            args[attr].append(part)

    command_args = {}
    for flag, value in args.iteritems():
        if len(value) == 1:
            value = value[0]
        command_args[flag] = value
    return command_args


def _is_number(string):
    '''
    Return True if the string can be cast to a digit/float, otherwise return False
    '''
    try:
        float(string)
        return True
    except ValueError:
        return False


def scrape_palette_node(palette_node, palette_filepath):
    '''
    Inspect/scrape the xgen palette node and parse it's associated .xgen file for file dependencies
    named.
    '''
    file_paths = []
    match = re.match("(.+)\.xgen", palette_filepath)
    if match:
        abc_patch_file = cmds.file("%s.abc" % (match.group(1)), expandName=True, query=True, withoutCopyNumber=True)
        if os.path.isfile(abc_patch_file):
            file_paths.append(abc_patch_file)

    logger.debug("scraping dependencies for xgen file: %s", palette_filepath)
    palette_dependencies = scrape_xgen_file(palette_filepath)
    return file_paths + palette_dependencies


def scrape_xgen_file(filepath):
    '''
    Scrape the given .xgen file for file dependencies.
    '''
    try:
        palette_modules = parse_xgen_file(filepath)
    except Exception:
        logger.exception("Failed to parse XGen Palette file: %s", filepath)
        return []

    resources = common.load_resources_file()
    xgen_attrs = resources.get("xgen_dependency_attrs") or {}

    paths = []

    for module_type, module_attrs in xgen_attrs.iteritems():
        for module in palette_modules.get(module_type, []):
            for module_attr_info in module_attrs:
                for module_attr, attr_conditions in module_attr_info.iteritems():
                    logger.debug("Scraping %s.%s", module_type, module_attr)
                    if _are_conditions_met(module, attr_conditions or {}):
                        value = module.get(module_attr, "")
                        # Convert the raw parsed string value to a list of values (split by whitespace),
                        # filtering out any empty values.
                        values = filter(None, [v.strip(' \t\r\n') for v in value.split()])
                        if values:
                            # Use the last item in the values. This is a huge assumption (that we'll always
                            # only want the last item, but it's the best we have without a proper
                            # xgen api
                            path = values[-1]
                            logger.debug("Found: %s", path)
                            if not os.path.isfile(path):
                                logger.warning("Path does not exist, skipping: %s", path)
                                continue
                            paths.append(path)
    return paths


def _are_conditions_met(module, attr_conditions):
    '''
    Return True if the all of the given conditions are met for the the given xgen module values
    '''
    for condition_attr, condition_value in attr_conditions.iteritems():
        if module.get(condition_attr) != condition_value:
            logger.debug("Condition: %r != %r", module.get(condition_attr), condition_value)
            return False
    return True


def parse_xgen_file(filepath):
    '''
    TODO(LWS): I hope we can get rid of this ASAP if/when xgen provides an api to read .xgen files

    Crude .xgen file parser for reading palette files.

    Return a dictionary where the key is the module type, and the value is a list of modules of that
    type.  Each module is a dictionary of data, where the key is the property/attribute name, and the
    value is the raw value of the property.

    example input file content:

        Palette
            name            robert_xgen_coll
            parent
            xgDataPath        /test/robert/collections/robert_xgen_coll
            xgProjectPath        /test/shot_100/lighting/
            xgDogTag
            endAttrs

    example output:
       {"Palette": [
           {
              'name': 'robert_xgen_coll',
              'parent': '',
              'xgDataPath': '/test/robert/collections/robert_xgen_coll',
              'xgDogTag': '',
              'xgProjectPath': '/test/shot_100/lighting/',
              'endAttrs': '',
           }
        ]}

    '''
    modules = []

    # First we parse each line to segregate them into groups of lines, where each group represents
    # a diffent section (module).
    with open(filepath) as f:
        module = []
        for line in f:
            # Strip the line of all leading/trailing whitepace characters
            line = line.strip(' \t\r\n')
            # If the line is empty, it could mean that we're at the end of a module definition.
            # If so, add the module to the list of modules, and create an empty new one.
            # Otherwise ignore the blank line and continue parsing.
            if not line:
                if module:
                    modules.append(module)
                    module = []
                continue
            # skip any comments, and the fiile version
            if line.startswith("#") or line.startswith('FileVersion'):
                continue
            module.append(line)

    # Parse each grouping of lines into a dictionary that represents a single module.
    # Each dictionary key is an attribute/property of the module.

    # Create an empty dictionary which has list as default values
    parsed_modules = collections.defaultdict(list)
    for module in modules:
        parsed_module = {}
        # The first line of the module defines the module type
        module_type = module.pop(0).strip(' \t\r\n')
        # The rest of the lines represent a property on the module
        for line in module:
            # Split the line by the first whitespace
            parts = [v.strip() for v in line.split(None, 1)]
            # Use the first item as the attr name, and the rest as the attr value
            attr_name = parts.pop(0)
            # Its possible that there is no value entry, so must take that into consideration.
            attr_value = parts[0] if parts else ""

            parsed_module[attr_name] = attr_value
        parsed_modules[module_type].append(parsed_module)

    return dict(parsed_modules)


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
