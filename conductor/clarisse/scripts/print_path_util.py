import ix

def main():
    """Remove drive letters from all paths."""
    attrs = ix.api.OfAttr.get_path_attrs()
    count = len(list(attrs))
    ix.log_info("File contains {:d} path references".format(count))
    for attr in attrs:
        path = attr.get_string()
        atname = attr.get_name()
        objname = attr.get_parent_object().get_name()
        ix.log_info("{}.{}={}".format(objname, atname, path))
main()
