import re
import ix

LETTER_RX = re.compile(r'^([a-zA-Z]):')


def _strip_drive_letter(attr):
    path = attr.get_string()
    atname = attr.get_name()
    objname = attr.get_parent_object().get_name()

    if path and LETTER_RX.match(path):
        ix.log_info("Strip: {}.{} {}".format(objname, atname, path))
        attr.set_string(re.sub(LETTER_RX, "", path))
        return True
    return False


def main():
    """Remove drive letters from all paths."""
    attrs = ix.api.OfAttr.get_path_attrs()
    total = len(list(attrs))
    ix.log_info("Stripping drive letters for {:d} paths".format(total))
    count = 0
    for attr in attrs:
        if _strip_drive_letter(attr):
            count += 1
    ix.log_info(
        "Done stripping {:d} of {:d} drive letters".format(count, total))


main()
