import os
import logging
import re
import subprocess

import afpipe.utils
import afkatana.publish

import Katana
from Katana import NodegraphAPI, FarmAPI, KatanaFile, Nodes3DAPI, Nodes2DAPI, PluginSystemAPI, RenderingAPI

from Katana import NodegraphAPI, FarmAPI, KatanaFile, Nodes3DAPI, Nodes2DAPI

DEPS = {
        'Alembic_In':{'params':['abcAsset']},
        'LiveGroup':{'params':['source']},
        'LookFileMaterialsIn':{'params':['lookfile']},
        'LookFileAssign':{'params':['args.lookfile.asset.value']},
        'LookFileGlobalsAssign':{'params':['args.lookfile.asset.value']},
        'ScenegraphXml_In':{'params':['asset']},
        'AttributeJson_In':{'params':['filepath']},
        'GIBake':{'params':['user.Read.Irradiance', 'user.Read.LightMap']},
        'VrayShadingNode':{'params':['parameters.file.value', 'parameters.filename.value'], 'item_class':afpipe.publish.TextureItem},
        'AttributeSet':{'params':['stringValue', 'groupValue'], 'item_class':afpipe.publish.TextureItem},
        'Group':{'params':{'user':{}, 'hdr':{'item_class':afpipe.publish.HDRItem}}},
        }

logger = logging.getLogger(__name__)

def get_renderers():
    '''
    Return a list or registered renderer plugin names 
    
    e.g. ['vray']
    
    '''
    return PluginSystemAPI.PluginCache.GetPluginNames()["RenderPlugin"]


def get_renderer_info(renderer_name):
    '''
    For the given renderer, return its plugin version
    
    e.g. "VRay for katana"
    '''

def get_katana_version():
    '''
    Return the version of katana that is currently running.
    
    e.g. "2.0v4"
    
    '''

    return os.environ.get("KATANA_RELEASE", "")


def get_output_dirpath(render_node):
    ''' 
    Given a render node object, extract the base output directory.
    '''
    cur_frame = NodegraphAPI.GetCurrentTime()

    output_paths = set()  # use this just for logging/feedback purposes
    output_dirpaths = set()
    for param in render_node.getParameters().getChild('outputs').getChild('locations').getChildren():
        output_path = param.getValue(cur_frame)
        if output_path:
            output_paths.add(output_path)
            output_dirpath = os.path.dirname(output_path)
            if output_dirpath.startswith('/Volumes/af/'):  # Filter to only accept output directories which exist in /Volumes/af/
                output_dirpaths.add(output_dirpath)

    if output_dirpaths:
        common_dir = os.path.commonprefix(output_dirpaths).rstrip('/')
        if not common_dir or common_dir == "/":
            raise Exception("Render node %s has more than one output "
                            "directory root! Your files would not be downloaded!\n"
                            "Output paths:\n\t%s" % (render_node.getName(), "\n\t".join(output_paths)))
        return common_dir


def get_frame_range():
    '''
    Return the start and end time of the katana file as a tuple of ints
    '''
    return NodegraphAPI.GetWorkingInTime(), NodegraphAPI.GetWorkingOutTime()


def get_katana_filepath():
    '''
    Get the filepath for the currently open katana file
    '''
    # Query katana for the currently open katana file
    katana_filepath = FarmAPI.GetKatanaFileName()

    if not katana_filepath or not os.path.isfile(katana_filepath):
        raise Exception("Current Katana file has not been saved or does not exist! %s" % katana_filepath)
    return katana_filepath




def collect_dependencies(katana_filepath, render_node):
    '''
    Return a list of filepaths that the current katana scene has dependencies on.
    This is achieved by inspecting katana's nodes.  
    '''
    content_filepaths = get_content_filepaths(katana_filepath, render_node.getName())
    pipeline_filepaths = get_pipeline_filepaths()

    # we have to save because we may have changed the scebe (Sg xml and symlink paths)
    KatanaFile.Save(FarmAPI.GetKatanaFileName())

    return content_filepaths + pipeline_filepaths

def get_content_filepaths(katana_filepath, render_node):
    '''
    Return the filepaths for all dependencies for the render node as 
    well as any other Katana Resources directories
    '''
    logger.info("Collecting dependencies for render node: %s", render_node)

    # Get dependencies
    raw_paths = afkatana.publish.Scene().getDependencies(use_wildcard=True,
                                            fix_params=True,
                                            render_nodes=[NodegraphAPI.GetNode(render_node)]).keys()

    # append the katana filepath
    raw_paths.append(katana_filepath)

    paths = []
    logger.info("Collecting dependencies for render node: %s", render_node)
    # Remove any dependencies which are invalid (don't exist on disk, or are in invalid location)
    for path in raw_paths:
        # Only path supported on Conductor
        if not path.startswith('/Volumes/af/') :
            logger.warning("Skipping dependency: %s", path)
            continue


        # Check whether the file exists.
        # TODO: Note that this will sometimes erroneously evaluate to True
        # When the file doesn't actually exist on disk. This happens under
        # the following circumstances:
        #   1. The file is named using an image sequence notation.
        #   2. There is a file on disk the same directory which matches
        #      the same image sequence notation (but represents a different frame)
        if afpipe.utils.getFileObject(path).exists():
            logger.info("Adding as job dependency: %s", path)
            paths.append(path)
        else:
            logger.warning("Dependency does not exist on disk. Excluding as job dependency: %s", path)

    return paths


def get_pipeline_filepaths():
    '''
    Return the filepaths for all code/pipeline/tool dependencies for the 
    currently opened katana file
    '''
    return afpipe.utils.Env().getConductorDependencies(['katanatools', 'vraytools', 'nuketools', 'tractortools'], ['NUKE_PATH'])



def get_render_nodes():

    return NodegraphAPI.GetAllNodesByType("Render")





def generate_env():
    '''
    Generate a dictionary of environment variables that will be set for the
    Conductor job. 
    
    Note that the dictionary values can refer to existing environment variables
    that are found in Conductor's environment
    
    example:
        {"PYTHONPATH":"/tmp/python:$PYTHONPATH"}
      
    '''
    conductor_env = {}
    for var_name, var_value in sorted(afpipe.utils.Env().asConductor().iteritems()):
        conductor_env[var_name] = var_value
    return conductor_env


