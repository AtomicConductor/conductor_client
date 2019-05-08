import ix
import re

LETTER_RX = re.compile(r'^([a-zA-Z]):')

def _strip_drive_letter(attr):
    path = attr.get_string()
    if path:
        name =  attr.get_name()
        print "Strip letter from path: {} of attr: {}".format(path, name)
    attr.set_string(re.sub(LETTER_RX, "", path))

def main():
    """Remove drive letters from all paths."""
    print ("Resolving drive letter file paths")
    for attr in ix.api.OfAttr.get_path_attrs():
        print ("Resolving attrs {}".format(attr.get_name()))
        _strip_drive_letter(attr)


main()
