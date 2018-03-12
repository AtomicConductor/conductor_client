import sys
import os
import argparse

from conductor.houdini.lib.sequence import Sequence

# def error(msg, exit=True):
#     if msg:
#         sys.stderr.write('\n')
#         sys.stderr.write('Error: %s\n' % msg)
#         sys.stderr.write('*****')

#     sys.stderr.write('\n')
#     if exit:
#         sys.exit(1)


 

def parse_args():

    parser = argparse.ArgumentParser(add_help=False)

    # driver
    parser.add_argument('-d', dest='driver', required=True)

    # range
    parser.add_argument('-r', dest='range', required=True)
 
    # output file
    parser.add_argument('-o', dest='output')

    # input hipfile
    parser.add_argument('-f', dest='hipfile', required=True)

    args, unknown = parser.parse_known_args()

    # Handle unknown arguments (show usage text and exit)
    if unknown:
        parser.usage()
        sys.exit(1)

    return args
 
def render():
    hou.hipFile.load("/Users/julian/projects/conductor/arntest.hip")
    rop_node = hou.node("/out/arnold1")
    for f in [1, 3, 4, 8, 9]:
        fn = "/Users/julian/projects/conductor/render/blah.%d.exr" % f
        rop_node.render(
            frame_range=(
                f,
                f),
            output_file=fn,
            verbose=True,
            output_progress=True)


args = parse_args()
print args