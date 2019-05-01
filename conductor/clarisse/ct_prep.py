import ix
import re

LETTER_RE = re.compile(r'^([a-zA-Z]):')

def _strip_drive_letter(attr):
    path =  attr.get_string()
    print "Stripping letter from ", path
    attr.set_string(re.sub(LETTER_RE, "", path))

def main():

    contexts = ix.api.OfContextSet()
    ix.application.get_factory().get_root().resolve_all_contexts(contexts)
    for context in contexts:
        if context.is_reference():
            attr = context.get_attribute("filename")
            _strip_drive_letter(attr)

    for attr in ix.api.OfAttr.get_path_attrs():
        _strip_drive_letter(attr)


main()