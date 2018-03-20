#!/usr/bin/env hython

import sys
import os
import argparse

from conductor.houdini.lib.sequence import Sequence
from conductor.houdini.lib.clump import Clump

OUTPUT_DIR_PARMS = {
    "ifd": "vm_picture",
    "arnold": "ar_picture",
    "ris":  "ri_display"
}


def error(msg):
    if msg:
        sys.stderr.write('\n')
        sys.stderr.write('Error: %s\n' % msg)
        sys.stderr.write('\n')
        sys.exit(1)


def usage(msg=""):
    print "USAGE"
    error(msg)


def parse_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-d', dest='driver', required=True)
    parser.add_argument('-r', dest='range', required=True)
    # parser.add_argument('-o', dest='output')
    parser.add_argument('-f', dest='hipfile', required=True)

    args, unknown = parser.parse_known_args()

    if unknown:
        usage('Unknown argument(s): %s' % (' '.join(unknown)))
    return args


def make_output_directory(rop):
    print "making output directory"
    directory = os.path.join( hou.getenv("JOB"), "render")

    rop_type =rop.type().name() 
    parm_name = OUTPUT_DIR_PARMS.get(rop_type)
    if parm_name:
        path = rop.parm(parm_name).eval()
        ov_dir = os.path.dirname(path)
        if ov_dir:
            directory = ov_dir

    if not os.path.exists(directory):
        os.makedirs(directory)

def render(args):

    sys.stderr.write('render\n')

    print "args.hipfile: %s" % args.hipfile
    print "args.driver: %s" % args.driver
    print "args.range: %s" % args.range
    # print "args.output: %s" % args.output
    sys.stderr.write('Here 1\n')
    
    try:
        seq = Sequence.from_spec(args.range)
    except ValueError as err:
        usage(str(err))
    
    clumps = Clump.regular_clumps(seq)

    sys.stderr.write('Here 2\n')

    try:
        hou.hipFile.load(args.hipfile)
    except hou.LoadWarning as e:
        print e
    sys.stderr.write('Here 3\n')

    rop = hou.node(args.driver)
    if not rop:
        usage('Rop does not exist: %s' % args.driver)
    
    sys.stderr.write('Here 4\n')

    make_output_directory(rop)

    sys.stderr.write('Here 5\n')

    for clump in clumps:
        cmd = "render "
        rop.render(
            frame_range=clump.range,
            verbose=True,
            output_progress=True,
            method=hou.renderMethod.FrameByFrame
        )

    sys.stderr.write('Here 6 FIN\n')


sys.stderr.write('****************************\n')
sys.stderr.write('START\n')
 
args = parse_args()
render(args)
sys.stderr.write('DONE\n')
sys.stderr.write('*-------------------------*\n')