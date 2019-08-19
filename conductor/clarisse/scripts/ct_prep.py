import re
import os
import ix
import argparse
import errno
import sys

LETTER_RX = re.compile(r'^([a-zA-Z]):')


def main():
    """Remove drive letters from all paths."""
    desc = "Prepare a Clarisse project file for rendering on Conductor"
    parser = argparse.ArgumentParser(description=desc)

    parser.add_argument('-strip_drive_letters', action='store_true',
                        default=True,
                        help='If this was submitted from windows, strip drive letters.')

    parser.add_argument('-range', nargs=2, type=int,
                        help='Ensure image ranges are turned on.')

    parser.add_argument('-images', nargs='+', type=str,
                        help='Image object names.')

    options, unknowns = parser.parse_known_args()
    ix.log_info("strip_drive_letters {}".format(options.strip_drive_letters))
    if options.strip_drive_letters:
        strip_drive_letters()

    if options.range and options.images:
        start, end = options.range
        force_image_ranges(start, end, options.images)

    ensure_image_directories(options.images)


def strip_drive_letters():
    attrs = ix.api.OfAttr.get_path_attrs()
    total = len(list(attrs))
    ix.log_info("Stripping drive letters for {:d} paths".format(total))
    count = 0
    for attr in attrs:
        if strip_drive_letter(attr):
            count += 1
    ix.log_info(
        "Done stripping {:d} of {:d} drive letters".format(count, total))


def strip_drive_letter(attr):
    path = attr.get_string()
    atname = attr.get_name()
    objname = attr.get_parent_object().get_name()

    if path and LETTER_RX.match(path):
        ix.log_info("Strip: {}.{} {}".format(objname, atname, path))
        attr.set_string(re.sub(LETTER_RX, "", path))
        return True
    return False


def force_image_ranges(start, end, images):
    # Clarisse doesn't respect frame range overrides, so we make sure the image ranges
    # are covered.
    ix.log_info(
        "Ensuring image ranges are on for the sequence {}:{}".format(start, end))
    for image_path in images:
        image = ix.get_item(image_path)
        ix.log_info("Setting range for: {} ".format(
            image.get_name()))
        image.get_attribute("first_frame").set_long(start)
        image.get_attribute("last_frame").set_long(end)
        image.get_attribute("frame_step").set_long(1)


def ensure_image_directories(images):
    """Clarisse fails to render if the destination
    directories don't exist"""
    ix.log_info("Ensure directories exist for images")
    directories = []
    for image_path in images:
        image = ix.get_item(image_path)
        directories.append(os.path.dirname(
            image.get_attribute("save_as").get_string()))

    mkdir_p(directories)


def mkdir_p(dirs):
    """Make directories unless they already exist."""
    for d in dirs:
        try:
            os.makedirs(d)
            sys.stdout.write("Made Directory:{}\n".format(d))
        except OSError as ex:
            if ex.errno == errno.EEXIST and os.path.isdir(d):
                pass
            else:
                raise


main()
