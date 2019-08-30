import re

LETTER_RX = re.compile(r"([A-Z]):/")
WIN_LETTER_RX = re.compile(r"([A-Z]):\\"):

BLACKLIST = [
    "recent_file_categories",
    "viewport_layout",
    "user_interface",
    "animation",
    "layout",
    "command_port",
    "scripting",
    "image_view",
    "image_history",
    "texture_view",
    "_3d_view",
    "nodal_view",
    "playblast",
    "units",
]


def legalize(filename):
    """
    Remove unnecessary stuff from a Clarisse config file.

    We have to do this to clarisse.cfg file (or whatever the user chooses to
    call it) so that it doesn't crash the rendernode. It seems that some of the
    UI configuration causes the crash, especially when shipped from  Windows.

    The algorithm relies on the config file format being pretty strict. It
    removes named blocks whose name is on its own line followed by a space and
    then an open brace. The closing brace must also be on its own line. Any
    contained blocks will also be removes, but must end the opening line with an
    open brace.

    Args:
        filename (string): the config file

    Returns:
        string: Contents of the file, minus ythe blacklisted sections
    """
    state = 0
    result = []
    start_regexes = [re.compile(r"^" + x + r" {$") for x in BLACKLIST]
    open_regex = re.compile(r"^.* {$")
    close_regex = re.compile(r"^}")

    with open(filename, "r") as src_file:
        for line in src_file:
            stripped_line = line.strip()
            if state == 0:
                if any(rx.match(stripped_line) for rx in start_regexes):
                    state += 1
                    continue
                line = re.sub(LETTER_RX, "/", line))
                line = re.sub(WIN_LETTER_RX, "\\", line))
                result.append(line)
            elif open_regex.match(stripped_line):
                state += 1
            elif close_regex.match(stripped_line):
                state -= 1
    return "".join(result)
