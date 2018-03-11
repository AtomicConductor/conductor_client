import sys
import os
import argparse


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
   
    # range_type
    parser.add_argument('-t', dest='type', required=True, choices=['regular', 'irregular'])

    # output file
    parser.add_argument('-o', dest='output', required=True)

    # input hipfile
    parser.add_argument('-f', dest='hipfile', required=True)




    # Option arguments
    # parser.add_argument('-c', dest='c_option')

    # parser.add_argument('-i', dest='i_option', type=int)
    # parser.add_argument('-t', dest='t_option')
    # parser.add_argument('-o', dest='o_option')
    # parser.add_argument('-b', dest='b_option', type=float)
    # parser.add_argument('-j', dest='threads', type=int)
    # parser.add_argument('-F', dest='frame', type=float)
    # parser.add_argument('-f', dest='frame_range', nargs=2, type=float)

    # # .hip|.hiplc|.hipnc file
    # parser.add_argument('file', nargs='*')

    # # Boolean flags
    # parser.add_argument('-e', dest='e_option', action='store_true')
    # parser.add_argument('-R', dest='renderonly', action='store_true')
    # parser.add_argument('-v', dest='v_option', action='store_true')
    # parser.add_argument('-I', dest='I_option', action='store_true')

    args, unknown = parser.parse_known_args()

    # Handle unknown arguments (show usage text and exit)
    if unknown:
        usage('Unknown argument(s): %s' % (' '.join(unknown)))

    # If there's something wrong with the arguments, show usage and exit.
    # err = validate_args(args)
    # if err:
    #     usage(err)

    return args


# hrender -e  -f 1 10  -d /out/arnold1  arntest.hip


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
# render(args)
