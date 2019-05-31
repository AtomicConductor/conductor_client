#!python

import argparse
import functools
import logging
import os
import shlex
import sys
import time


import lx
# Reasign for brevity. unfortunately we can't import from the symbol module bc it's a builtin
C = lx.symbol

import modo


# Obtained from querying modo api. See  "query hostservice class.servers ? saver"
FORMATS = (
    '$FLEX',
    '$ImageCine',
    '$LXOB',
    '$NLWO2',
    '$Targa',
    '$X3D',
    'Alembic',
    'AlembicHDF',
    'BMP',
    'COLLADA_141',
    'DXF',
    'HDR',
    'HPGL_PLT',
    'JPG',
    'LayeredPSD',
    'PNG',
    'PNG16',
    'PSD',
    'PSDScene',
    'SGI',
    'SVG_SceneSaver',
    'THREEDM',
    'TIF',
    'TIF16',
    'TIF16BIG',
    'fbx',
    'fbx2015',
    'gltf.bin',
    'gltf.gltf',
    'openexr',
    'openexr_32',
    'openexr_tiled16',
    'openexr_tiled32',
    'openexrlayers',
    'openexrlayers32',
    'pySTLScene2',
    'vs_GEO',
    'wf_OBJ',
)


logger = logging.getLogger("conductor.modo")


class ExitOnException(object):
    def __call__(self, orig_function):
        @functools.wraps(orig_function)
        def wrapper_function(*args, **kwargs):
            try:
                exit_value = None
                return orig_function(*args, **kwargs)
            except Exception as e:
                exit_value = "LXe_FAILED:%s" % e
                logger.exception("")
            finally:
                lx.eval("app.quit")
                sys.exit(exit_value)

        return wrapper_function


def parse_args(args):

    # create the main parser. Not sure why this parser is required, but got parsing tracebacks when excluding it (it gets confused about the arguments provided)
    parser = argparse.ArgumentParser(
        prog="conductor_render",
        description="< description placeholder >",
    )

    parser.add_argument(
        "--modo-filepath",
        help="<help placeholder>",
    )

    parser.add_argument(
        "-s", "--frame-start",
        type=int,
        help="<help placeholder>",
    )

    parser.add_argument(
        "-e", "--frame-end",
        type=int,
        help="<help placeholder>",
    )

    parser.add_argument(
        "--frame-step",
        type=int,
        help="<help placeholder>",
    )

    parser.add_argument(
        "-o", "--output-path",
        required=True,
        dest='output_dirpath',
        help="<help placeholder>",
    )

    parser.add_argument(
        "-x", "--res-x",
        type=int,
        dest='resolution_x',
        help="<help placeholder>",
    )

    parser.add_argument(
        "-y", "--res-y",
        type=int,
        dest='resolution_y',
        help="<help placeholder>",
    )

    parser.add_argument(
        "--file-format",
        choices=FORMATS,
        help="<help placeholder>",
    )
    parser.add_argument(
        "-p", "--project-dir",
        dest='project_dirpath',
        help="<help placeholder>",
    )
    parser.add_argument(
        "--output-pattern",
        help=("The output file naming pattern"
              "<output> - names the file for the render output item (uses the actual name specified for the Render Output item in the Shader Tree)."
              "<pass> names the file for the Render Pass."
              "<F> is the frame number (add an extra F for extra leading zeros)."
              "<none> Disables the output pattern"
              "example"
              "[.<pass>][.<output>][.<LR>].<FFFF>"),
    )

    parser.add_argument(
        "--render-pass-group",
        help="<help placeholder>",
    )
    return parser.parse_args(args=args)


def run_modo_render(output_dirpath, frame_start=None, frame_end=None, frame_step=None, resolution_x=None, resolution_y=None, file_format=None, output_pattern=None, render_pass_group=None):
    '''

    Deconstruction of the path of rendered file:

    Example path:  /tmp/modo/thing.beauty.0001.exr

    - Output Filename (filename):      /tmp/modo/thing
    - Output Pattern (outPat):         .beauty.0001
    - Format (format)                  .exr
    '''
    scene = modo.Scene()

    if render_pass_group is not None:
        for group in scene.renderPassGroups:
            if group.name == render_pass_group:
                render_pass_group = group.id
                break
        else:
            raise Exception("Specified Render Pass Group does not exist: %s" % render_pass_group)

    # -------------------------------
    # Global/scene Render settings
    # -------------------------------

    attr_names = {
        C.sICHAN_POLYRENDER_FIRST: frame_start,
        C.sICHAN_POLYRENDER_LAST: frame_end,
        C.sICHAN_POLYRENDER_STEP: frame_step,
        C.sICHAN_POLYRENDER_RESX: resolution_x,
        C.sICHAN_POLYRENDER_RESY: resolution_y,
        C.sICHAN_POLYRENDER_OUTPAT: output_pattern,
    }

    render_item = scene.renderItem
    for attr_name, attr_value in attr_names.iteritems():
        if attr_value is not None:
            logger.info("Setting %s: %s", attr_name, attr_value)
            render_item.channel(attr_name).set(attr_value)

    # -------------------------------
    # Render Item settings
    # -------------------------------

    # Get the current output filename
    for output_item in scene.items(itype=modo.c.RENDEROUTPUT_TYPE):

        # Output filename
        old_output_filename = output_item.channel(C.sICHAN_RENDEROUTPUT_FILENAME).get()
        old_output_dirpath, filename_prefix = os.path.split(old_output_filename)
        logger.info('Changing %s "%s" output directory from: %s  to: %s', output_item.type, output_item.name, old_output_dirpath, output_dirpath)
        new_output_filename = os.path.join(output_dirpath, filename_prefix)

        logger.info('New new_output_filename: %s', new_output_filename)
        output_item.channel(C.sICHAN_RENDEROUTPUT_FILENAME).set(new_output_filename)

        # Output file format
        if file_format is not None:
            logger.info('Setting format to: %s', file_format)
            output_item.channel(C.sICHAN_RENDEROUTPUT_FORMAT).set(file_format)

    render(filename=new_output_filename, file_format=file_format, render_pass_group=render_pass_group)


def render(filename, file_format=None, options=None, render_pass_group=None):
    '''
    filename:
        required.  Modo doesn't seem to respect/inherit the settings from the scene file, so filename must be specified 


     <filename:string> <format:string> <options:integer> <group:&item>

     e.g. render.animation * * group:group003

    format:
        doesn't appear to be respected by this command.  Set this for each render output item istead.

    options:
        Generally not anything useful for the end user (mostly for internal modo development).
        Logically OR'ed together:
            (1) NO_WAITING 
            (2) NO_IMAGE, 
            (4) NO_CLEANUP 
            (8) IC_ONLY     (irradiance computation only)

    group:  (Render Pass Group)
        A render pass group is a grouping of render passes


    NOTE: Using lx.command doesn't seem to work properly:
        - Doesn't respect the output pattern (set earlier)
        - Doesn't respect the format arg.

    '''

    # Use braces around filename because it may contain quotes, spaces, etc
    #    -Note that filepaths that contain curly braces in them will NOT work.
    #     It appears that there is no way to render to a filepath that contains both spaces and braces?
    # DO NOT use braces around the group (render pass group) argument. This will break group identification functionality

    cmd = 'render.animation filename:{%s}' % filename

    if file_format is not None:
        cmd += " format:%s" % file_format

    if options is not None:
        cmd += " options:%s" % options

    if render_pass_group is not None:
        cmd += " group:%s" % render_pass_group

    logger.info(cmd)
    return lx.eval(cmd)


@ExitOnException()
def main():
    logger.debug("lx.arg: %s", lx.arg())
    args = vars(parse_args(shlex.split(lx.arg())))
    for arg_name, arg_value in sorted(args.iteritems()):
        logger.debug("%s: %s", arg_name, arg_value)

    # Set the modo project if one has been specified
    project_dirpath = args.pop("project_dirpath", None)
    if project_dirpath:
        logger.info("Setting modo project to: %s", project_dirpath)
        lx.command("projdir.chooseProject", path=project_dirpath)

    # Open the modo file if one has been specified, otherwise assume to use the currently active/open one.
    modo_filepath = args.pop("modo_filepath", None)
    if modo_filepath:
        logger.info("Opening %s", modo_filepath)
        lx.command("scene.open", filename=modo_filepath)

    run_modo_render(**args)


def wait(seconds):
    logger.info("waiting for %s seconds", seconds)
    for _ in range(int(seconds)):
        sys.stdout.write(" .")
        time.sleep(1)


if __name__ == "__main__":
    lx.eval("log.toConsole true")
    lx.eval("log.toConsoleRolling true")
    logging.basicConfig(level=logging.DEBUG)
    # Wait for a few seconds before executing any modo commands.
    # This is a hack/work-around for a bug where modo will oftentimes (~30% of the time) hang
    # when starting. The theory is that there is a window of time where modo hasn't fully initialized yet,
    # and if you issue commands to it before it's ready, it will cause modo to hang.
    wait(5)
    main()
