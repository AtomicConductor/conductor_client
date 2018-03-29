#!/usr/bin/env hython


"""Script to render a ROP.

Currently it is designed for images, but can be extended to
produce output for other ROPs
"""
import sys
import argparse
import hou


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
    -f file             The hipfile containing the driver to render
    """
    error(msg)


def validate_args(args):
    """Check arg values such as hip and rop existence etc.

    TODO: Implement these validations and remove inline checks
    from render method.
    """
    return ""


def parse_args():
    """Parse args and error if any are missing or extra."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-d', dest='driver', required=True)
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
    """

    try:
        hou.hipFile.load(args.hipfile)
    except hou.LoadWarning as e:
        print e

    rop = hou.node(args.driver)
    if not rop:
        usage('Rop does not exist: %s' % args.driver)

    rop.render(
        verbose=True,
        output_progress=True
    )


render(parse_args())
