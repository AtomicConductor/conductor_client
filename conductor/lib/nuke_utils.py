import logging
import os
import re

import nuke
from conductor.lib import ocio_utils, package_utils

logger = logging.getLogger(__name__)


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


def get_plugins_info():
    plugins_info = []
    for PluginClass in PLUGIN_CLASSES:
        if PluginClass.exists():
            plugins_info.append(PluginClass.get())
    return plugins_info

def scrape_ocio_dependencies():
    '''
    Find the ocio config file (if it exists) and scrape it for external file dependencies
    '''
    config_filepath = get_ocio_config_filepath()

    if config_filepath:
        paths = ocio_utils.parse_ocio_config_paths(config_filepath)
        return paths
    
    else:
        return []

def get_ocio_config_filepath():
    '''
    Return the OCIO config filepath from Nuke's root node.

    Only return the filepath if color management is set to use a custom OCIO
    config.
    '''
    
    ocio_config_path = None

    if nuke.toNode("root").knobs()["OCIO_config"].value() == "custom":
        ocio_config_path = resolve_knob_path(nuke.toNode("root").knobs()["customOCIOConfigPath"])    

    return ocio_config_path

def collect_dependencies(write_nodes, views, dependency_knobs=None):
    '''
    For the given Write nodes, traverse up their hierarchy to query any nodes
    for dependency filepaths and return them.

    Note that a path value found in a node/knob may contain tcl expressions that this function
    will resolve, e.g. a path value of:
        "[python {nuke.script_directory()}]/[value seq]/[value shot]/cat.####.jpg"
    may resolve to:
        "/tmp/conductor/nuke/010/010_250/cat.%04d.jpg

    write_nodes: a list of Write nodes (their node names) for which to collect
                 dependencies for.

    dependency_knobs: A dictionary of nuke node types (and their knob names) for
                      which to query for dependency paths, e.g.
                            {'Read':['file'],
                             'DeepRead':['file']}

    '''
    dependency_knobs = dependency_knobs or {}

    # A custom OCIO config is defined on the root node
    deps = set(scrape_ocio_dependencies())

    for node_name in write_nodes:
        if nuke.exists(node_name):
            write_node = nuke.toNode(node_name)
            for dep_node in get_node_dependencies(write_node):
                for knob_type in dependency_knobs.get(dep_node.Class(), []):
                    knob = dep_node.knob(knob_type)
                    if knob:

                        # Handle OCIOCDLTransform:  Skip node/knob if "read from file" is not enabled
                        if dep_node.Class() == "OCIOCDLTransform":
                            if not dep_node.knob("read_from_file").value():
                                logger.debug("Skipping %s", knob.fullyQualifiedName())
                                continue

                        # Resolve TCL expressions and relative paths
                        path = resolve_knob_path(knob)

                        if re.search("%[Vv]", path):
                            for view in views:
                                view_path = re.sub("%V", view, path)
                                view_path = re.sub("%v", view[0], view_path)
                                deps.add(view_path)
                        else:
                            deps.add(path)

    return sorted(deps)


def resolve_knob_path(knob):
    '''
    Resolve the knob value of any TCL expression and/or relative path
    Note that this does *not* resolve any frame number expressions.

    args:
        knob: any File_Knob object

    return: str. the resolved path value

    example paths:
        '[python {nuke.script_directory()}]/../images/sequences/02/image.%04d.jpg'
        '../images/sequences/[value this.name]/image.%04d.jpg'
        '../images/sequences/03/image.%04d.jpg'
        '../images/sequences/../sequences/03/image.%04d.jpg'
        ''
    '''
    raw_value = knob.value()
    logger.debug("Resolving tcl expressions (if any) on %s value: %r", knob.fullyQualifiedName(), raw_value)
    path = nuke.runIn(knob.node().fullName(), "nuke.tcl('return {%s}')" % raw_value.replace("'", "\\'"))

    # If the path is empty/none, simply return.  no further processing necessary
    if not path:
        return path or ""  # ensure we return str

    if not os.path.isabs(path):
        logger.debug("Resolving relative path: %s", path)

        # Join the relative path with the nuke script directory
        path = os.path.join(nuke.script_directory(), path)

    # Resolve any ellipses in the path (e.g. ../../  ).
    # Unfortunately this also normpaths it (which will change any forward slashes to backslashes
    # if on Windows). So we perform a secondary hack to force-replace backslashes.  This may have
    # unintended consequences (e.g. is there a case where we need/want to preserve backslashes on
    # linux?)
    path = os.path.abspath(path).replace('\\', "/")

    logger.debug("Resolved to: %s", path)
    return path


def get_node_dependencies(node, types=(), collected_deps=()):
    '''
    Recursively traverse (upwards) the given node's node-graph, aggregating a list
    of all of its contributing nodes.

    node: any nuke node object
    types: tuple of nuke node types (strings) to restrict the returned nodes to.
    collected_deps: tuple. This should not be used by the caller.  A running-record
         of the dependencies that have been collected thus  far (at any given
         point in the recursion process).

     return: tuple of Nuke node objects

    '''

    # Handle "Group" nodes as special case because (because it's a collection of of nodes.
    group_deps = ()
    if node.Class() == "Group":
        sub_nodes = node.nodes()
        for sub_node in sub_nodes:
            group_deps = group_deps + get_node_dependencies(sub_node, types=types,
                                                            collected_deps=collected_deps)

    # Get the parent\dependency nodes of the given node
    parent_deps = tuple(node.dependencies())
    new_deps = ()
    # Traverse each of these dependency nodes and find _their_ dependencies
    for parent_dep in parent_deps:
        # Do not traverse dependencies for a node that's already been traversed.
        # otherwise an infinite loop may occur.  Generally this isn't allowed
        # in Nuke's dag structure, but it can be achieved by other means (such
        # as using an expression that targets another node.
        if parent_dep not in collected_deps:
            # Add the dep to collected_deps BEFORE seeking its dependencies (prevents infinite loop).
            collected_deps = collected_deps + (parent_dep, )
            new_deps = new_deps + get_node_dependencies(parent_dep, types=types,
                                                        collected_deps=collected_deps)
    collected_deps = collected_deps + new_deps + tuple(parent_deps) + group_deps
    return tuple(set([d for d in collected_deps if not types or d.Class() in types]))  # TODO, if this was written properly there is probably no reason we should be getting redundant info (so no nead for a set() )


def get_nuke_script_filepath():
    filepath = nuke.root().name()
    if not filepath or not os.path.isfile(filepath):
        raise Exception("Nuke script has not been saved to a file location.  Please save file before submitting to Conductor.")
    return filepath


def check_script_modified():
    '''
    Check if the scene's been modified, and error out if it has been
    '''
    return nuke.root().modified()


def save_current_nuke_script():
    '''
    Save the current script
    '''
    return nuke.scriptSave()


def get_frame_range():
    '''
    Return the frame range found in Nuke's Project settings.
    '''
    first_frame = int(nuke.Root()['first_frame'].value() or 0)
    last_frame = int(nuke.Root()['last_frame'].value() or 0)
    return first_frame, last_frame


def get_views():
    '''
    Return a list of the views that are available in the scene.
    '''
    return nuke.views()


def get_all_write_nodes():
    '''
    Return a dictionary of all Write and Deep Write nodes that exist in the current
    Nuke script.  The dictionary key is the node name, and the value (bool) indicates
    whether the node is currently selected or not.
    '''
    write_nodes = nuke.allNodes(filter="Write")
    write_nodes.extend(nuke.allNodes(filter="DeepWrite"))
    # Filter out Write / DeepWrite nodes that are marked as disabled
    write_nodes = [node for node in write_nodes if not node['disable'].value()]
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

    # Resolve the path of any TCL expressions, or relative path
    return resolve_knob_path(node.knob("file"))


class NukeInfo(package_utils.ProductInfo):
    '''
    A class for retrieving version information about the current maya session.

    Will ultimately produce something like this
        {'product': 'nuke',
         'vendor': 'The Foundry',
         'version': '9.0v7'
         'major_version': '9',
         'minor_version': '0',
         'release_version': '7',
         'build_version': '',
         'host_product': '',
         'host_product_version': ''}

    '''
    product = "nuke"

    @classmethod
    def get_product(cls):
        '''
        Return the name of the product, e.g.

            "nuke"
        '''
        return cls.product

    @classmethod
    def get_vendor(cls):
        return "The Foundry"

    @classmethod
    def get_version(cls):
        '''
        Return the product version, e.g.

            "9.0v7"
        '''
        return nuke.env["NukeVersionString"]

    @classmethod
    def get_major_version(cls):
        '''
        Return the major version of the product, e.g.

            "9"
        '''
        return str(nuke.NUKE_VERSION_MAJOR)

    @classmethod
    def get_minor_version(cls):
        '''
        Return the minor version of the product, e.g.

            ""
        '''
        return str(nuke.NUKE_VERSION_MINOR or 0)

    @classmethod
    def get_release_version(cls):
        '''
        Return the minor version of the product, e.g.

            "SP4"
        '''
        return str(nuke.NUKE_VERSION_RELEASE or 0)

    @classmethod
    def get_build_version(cls):
        '''
        Return the minor version of the product, e.g. 

            "SP4"
        '''
        return ""


PLUGIN_CLASSES = []
