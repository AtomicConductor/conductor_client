"""
Pre render script to run inside clarisse on the render node.
Ensures images are renderable for the given range.
Ensures directories exist for renders.
"""
import argparse
import errno
import os
import re
import sys
from contextlib import contextmanager

import ix

LETTER_RX = re.compile(r"^([a-zA-Z]):")


def main():
    """
    Prepare this project to be rendered.
    """
    desc = "Prepare a Clarisse project file for rendering on Conductor"
    parser = argparse.ArgumentParser(description=desc)

    parser.add_argument(
        "-range", nargs=2, type=int, help="Ensure image ranges are turned on."
    )

    parser.add_argument("-images", nargs="+", type=str, help="Image object names.")

    options, _ = parser.parse_known_args()

    if options.range and options.images:
        start, end = options.range
        force_image_ranges(start, end, options.images)

        ensure_image_directories(options.images)


def force_image_ranges(start, end, images):
    """
    Ensure the sequence attributes on image ranges are valid.

    Clarisse doesn't respect frame range overrides, so we make sure the image
    ranges are covered.

    Args:
        start (int): first frame
        end (int): last frame
        images (list): Clarisse paths to all images
    """

    ix.log_info(
        "Ensuring image ranges are on for the sequence {}:{}".format(start, end)
    )
    for image_path in images:
        image = ix.get_item(image_path)
        ix.log_info("Setting range for: {} ".format(image.get_name()))
        image.get_attribute("first_frame").set_long(start)
        image.get_attribute("last_frame").set_long(end)
        image.get_attribute("frame_step").set_long(1)


def ensure_image_directories(images):
    """
    Create directories in preparation for image output.

    Clarisse fails to render if the destination
    directories don't exist.

    Args:
        images (list): Clarisse paths to all images
    """

    ix.log_info("Ensure directories exist for images")
    directories = []
    for image_path in images:
        image = ix.get_item(image_path)
        directory = os.path.dirname(image.get_attribute("save_as").get_string())
        directories.append(directory)
        sys.stdout.write("{} save to disk at: {}\n".format(image_path, directory))
    mkdir_p(list(set(directories)))


def mkdir_p(dirs):
    """
    Make directories unless they already exist.

    Args:
        dirs (list): directories to create
    """
    for d in dirs:
        sys.stdout.write("Ensure directory: {} exists\n".format(d))
        try:
            os.makedirs(d)
            sys.stdout.write("Successfully made Directory:{}\n".format(d))
        except OSError as ex:
            if ex.errno == errno.EEXIST and os.path.isdir(d):
                sys.stdout.write("Directory exists: {}\n".format(d))
                pass
            else:
                sys.stderr.write(
                    "There's something wrong with the path: ('{}'), : {}\n".format(
                        d, os.strerror(ex.errno)
                    )
                )
                raise


main()
