import ix
import re

LETTER_RE = re.compile(r'^([a-zA-Z]):')


def _strip_drive_letter(attr):
    path = attr.get_string()
    print ("Stripping letter from {}".format(path))
    attr.set_string(re.sub(LETTER_RE, "", path))


def _resolve(ctx):
    """Strip drive letters from reference contexts.

    If a context (A) is a reference to another file and that file
    contains a reference contxt (B), and A's filepath is wrong, then we
    may not know anything about B, so we can't gather all contexts in one
    hit and replace drive letters. We must recurse down, and for each 
    reference context, resolve its path and then visit the contxts it
    contains.
    """
    print ("Resolving context recursively")
    level = ctx.get_level()
    if ctx.is_reference():
        attr = ctx.get_attribute("filename")
        _strip_drive_letter(attr)

    next_level = level + 1
    contexts = ix.api.OfContextSet()
    ctx.resolve_all_contexts(contexts)
    for ctx in [c for c in list(contexts) if c.get_level() == next_level]:
        _resolve(ctx)


def main():
    """Resolve all contexts and other filepaths."""
    print ("Resolving drive letter file paths")

    contexts = ix.api.OfContextSet()
    ix.application.get_factory().get_root().resolve_all_contexts(contexts)
    _resolve(contexts[0])

    for attr in ix.api.OfAttr.get_path_attrs():
        print ("Resolving attrs {}".format(attr.get_name()))
        _strip_drive_letter(attr)


main()
