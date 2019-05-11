import ix
import re

LETTER_RX = re.compile(r'^([a-zA-Z]):')

def _strip_drive_letter(attr):
    path = attr.get_string()
    atname = attr.get_name() 
    objname = attr.get_parent_object().get_name()
    ix.log_info("Ob:{} At:{} Val:{}".format( objname, atname, path))
    if path:
        attr.set_string(re.sub(LETTER_RX, "", path))


def main():
    """Remove drive letters from all paths."""
    attrs = ix.api.OfAttr.get_path_attrs()
    count = len(list(attrs))
    ix.log_info("Stripping drive letters for {:d} paths".format(count))
    for attr in attrs:
        _strip_drive_letter(attr)
    ix.log_info("Done stripping drive letters")

main()
