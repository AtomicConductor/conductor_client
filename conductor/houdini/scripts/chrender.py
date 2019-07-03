#!/usr/bin/env hython


"""Script to render a ROP.

Currently it is designed for images, but can be extended to
produce output for other ROPs
"""
import sys
import argparse
import hou

from sequence import Progression, Sequence


def error(msg):
    if msg:
        sys.stderr.write('\n')
        sys.stderr.write('Error: %s\n' % msg)
        sys.stderr.write('\n')
        sys.exit(1)


def usage(msg=""):
    print """Usage:

    All flags are required

    -d driver:          Path to the output driver that will be rendered
    -r range:           The frame range specification (see below)
    -f file             The hipfile containing the driver to render

    Frame range specification is a string which may be any number
    of ranges or single frame numbers separated by commas. A range
    may have an optional step parameter prefixed by "x" Examples:
    "1"
    "1,2,3,5,8"
    "3-7"
    "10-20x2"
    "3,6,7,10-20,30-60x3,9,34-40x2"

    """
    error(msg)


def validate_args(args):
    """Check arg values such as range, hip and rop existence etc.

    TODO: Implement these validations and remove inline checks
    from render method.
    """
    return ""


def parse_args():
    """Parse args and error if any are missing or extra."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-d', dest='driver', required=True)
    parser.add_argument('-r', dest='range', required=True)
    parser.add_argument('-f', dest='hipfile', required=True)

    args, unknown = parser.parse_known_args()

    if unknown:
        usage('Unknown argument(s): %s' % (' '.join(unknown)))

    err = validate_args(args)
    if err:
        usage(err)

    return args


def render(args):
    """Render the specified ROP.

    If there's anything drastically wrong with the args or
    the scene, exit. However, if there are only load
    warnings, print them and carry on. For example, the
    scene is likely to contain unknown assets such as the
    conductor job and submitter nodes, which were used to
    submit but are not needed to render.

    The rop render method taks a range (start, end, step).
    However, our range args are potentially an irregular set
    of frames. Therefore we convert the spec into arithmetic
    progressions and call the render command once for each
    progression.
    """
    try:
        seq = Sequence.create(args.range)
    except ValueError as err:
        usage(str(err))

    progressions = Progression.factory(seq)

    try:
        hou.hipFile.load(args.hipfile)
    except hou.LoadWarning as e:
        print e

    rop = hou.node(args.driver)
    if not rop:
        usage('Rop does not exist: %s' % args.driver)

    for progression in progressions:
        rop.render(
            frame_range=progression.range,
            verbose=True,
            output_progress=True,
            method=hou.renderMethod.FrameByFrame
        )


render(parse_args())
