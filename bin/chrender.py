import sys
import os
import argparse

from conductor.houdini.lib.sequence import Sequence
from conductor.houdini.lib.clump import Clump


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
    parser.add_argument('-o', dest='output')
    parser.add_argument('-f', dest='hipfile', required=True)
    
    args, unknown = parser.parse_known_args()

    if unknown:
        usage('Unknown argument(s): %s' % (' '.join(unknown)))
    return args

def enable_mkdir(rop):
    pass

def render(args):
    print "args.hipfile: %s" % args.hipfile
    print "args.driver: %s" % args.driver
    print "args.range: %s" % args.range
    print "args.output: %s" % args.output

    try:
        seq = Sequence.from_spec(args.range)
    except ValueError as err:
        usage(str(err))
    clumps = Clump.regular_clumps(seq)

    try:
        hou.hipFile.load(args.hipfile)
    except hou.LoadWarning as e:
        print e

    rop = hou.node(args.driver)
    if not rop:
        usage('Rop does not exist: %s' % args.driver)

    if args.output:
        rop.parm('vm_picture').set(args.output)
 
    for clump in clumps:
        cmd = "render "
        rop.render(
             frame_range=clump.range,
             verbose=True,
             output_progress=True)

args = parse_args()
render(args)