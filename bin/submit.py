#!/usr/bin/env python


import argparse
import getpass
import imp
import os
import sys
import yaml


try:
    imp.find_module('conductor')

except:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))


import conductor, conductor.setup
from conductor.setup import *
from conductor.lib import conductor_submit


def parseArgs():
    parser = argparse.ArgumentParser(description='parse submitter arguments',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cmd",
        help="execute this command.",
        type=str)
    parser.add_argument("--frames",
        help="frame range to execute over.",
        type=str)
    parser.add_argument("--user",
        help="Username to submit as",
        type=str,
        default=getpass.getuser(),
        required=False)
    parser.add_argument("--output_path",
        help="path to copy renders to",
        type=str,
        required=False)
    parser.add_argument("--upload_file",
        help="The path to an upload file",
        type=str,
        required=False)
    parser.add_argument("--upload_paths",
        help="Paths to upload",
        nargs="*")
    parser.add_argument("--resource",
        help="resource pool to submit jobs to, defaults to show name.",
        type=str,
        required=False)
    parser.add_argument("--cores",
        help="Number of cores that this job should run on",
        type=int,
        required=False)
    parser.add_argument("--priority",
        help="Set the priority of the submitted job. Default is 5",
        type=str,
        required=False)
    parser.add_argument("--upload_dependent",
        help="job id of another job that this should be upload dependent on.",
        type=str,
        required=False)
    parser.add_argument("--upload_only",
        help="Only upload the files, don't start the render",
        action='store_true')
    parser.add_argument("--force",
        help="Do not check for existing uploads, force a new upload",
        action='store_true')
    parser.add_argument("--postcmd",
        help="Run this command once the entire job is complete and downloaded",
        type=str,
        required=False)
    parser.add_argument("--skip_time_check",
        action='store_true',
        default=False,
        help="Don't perform a time check between local and cloud")
    parser.add_argument("--local_upload",
        help="Trigger files to be uploaded localy",
        action='store_true',
        required=False)

    return parser.parse_args()


def run_submit(args):
    # convert the Namespace object to a dictionary
    args_dict = vars(args)
    logger.debug('args_dict is %s', args_dict)
    submitter = conductor_submit.Submit(args_dict)
    submitter.main()


if __name__ == '__main__':
    args = parseArgs()
    run_submit(args)
