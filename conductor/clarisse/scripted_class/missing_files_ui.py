"""
Provide a window in which to display a MissingFiles.
"""

import ix


C_LEFT = ix.api.GuiWidget.CONSTRAINT_LEFT
C_TOP = ix.api.GuiWidget.CONSTRAINT_TOP
C_RIGHT = ix.api.GuiWidget.CONSTRAINT_RIGHT
C_BOTTOM = ix.api.GuiWidget.CONSTRAINT_BOTTOM

BTN_HEIGHT = 22
BTN_WIDTH = 100
WINDOW_LEFT = 600
WINDOW_TOP = 200
HEIGHT = 500
WIDTH = 800
PADDING = 5
TITLE_PANEL_HEIGHT = 90


SYMBOL_BUT_WIDTH = 30
CHECKBOX_WIDTH = 50

BOTTOM_BUT_WIDTH = WIDTH / 3


class MissingFilesWindow(ix.api.GuiWindow):
    """
    The entire window.

    Holds the panel plus buttons to Continue or Cancel.
    """

    def __init__(self, files):
        window_height = HEIGHT + BTN_HEIGHT

        super(MissingFilesWindow, self).__init__(
            ix.application.get_event_window(),
            WINDOW_LEFT,
            WINDOW_TOP,
            WIDTH,
            window_height,
            "Missing files",
        )

        self.result = False
        self.files = files

        self.title_widget = ix.api.GuiTextEdit(self, 0, 0, WIDTH, TITLE_PANEL_HEIGHT)
        self.title_widget.set_constraints(C_LEFT, C_TOP, C_RIGHT, C_TOP)
        self.title_widget.set_read_only(True)

        plural = len(files) > 1
        message = "Your project refers to {:d} {} exist on disk.\n".format(
            len(files), "files that do not" if plural else "file that does not"
        )
        message += "See the list of missing files below.\n\n"
        message += "You may continue the submission without {} or Cancel.".format(
            "them" if plural else "it"
        )
        self.title_widget.set_text(message)
        self.title_widget.set_font_size(14)

        self.text_widget = ix.api.GuiTextEdit(
            self, 0, TITLE_PANEL_HEIGHT, WIDTH, HEIGHT - TITLE_PANEL_HEIGHT
        )
        self.text_widget.set_constraints(C_LEFT, C_TOP, C_RIGHT, C_BOTTOM)

        self.text_widget.set_read_only(True)
        self.close_but = ix.api.GuiPushButton(
            self, 0, HEIGHT, BOTTOM_BUT_WIDTH, BTN_HEIGHT, "Cancel"
        )
        self.close_but.set_constraints(C_LEFT, C_BOTTOM, C_LEFT, C_BOTTOM)
        self.connect(self.close_but, "EVT_ID_PUSH_BUTTON_CLICK", self.on_close_but)

        self.spacer_but = ix.api.GuiPushButton(
            self, BOTTOM_BUT_WIDTH, HEIGHT, BOTTOM_BUT_WIDTH, BTN_HEIGHT, ""
        )
        self.spacer_but.set_constraints(C_LEFT, C_BOTTOM, C_RIGHT, C_BOTTOM)
        self.spacer_but.set_enable(False)

        self.go_but = ix.api.GuiPushButton(
            self,
            (WIDTH - BOTTOM_BUT_WIDTH),
            HEIGHT,
            BOTTOM_BUT_WIDTH,
            BTN_HEIGHT,
            "Continue",
        )
        self.go_but.set_constraints(C_RIGHT, C_BOTTOM, C_RIGHT, C_BOTTOM)

        self.connect(self.go_but, "EVT_ID_PUSH_BUTTON_CLICK", self.on_go_but)

        self._populate()

    def _populate(self):
        """
        Put the missing files in the window.
        """
        content = "\n".join(self.files)
        self.text_widget.set_text(content)

    def on_close_but(self, sender, eventid):
        """
        Hide UI so that the event loop exits and window is destroyed.
        """
        self.hide()

    def on_go_but(self, sender, eventid):
        """
        Set result and hide(destroy) the window.
        """
        self.result = True

        self.hide()


def proceed(files):
    """
    Show the window and pass in the missing file paths

    Args:
        files (list of strings): Unique, ready sorted, list of missing files.

    Returns:
        bool: whether or not the user wants to continue the submission or cancel.
    """
    if not files:
        return True
    win = MissingFilesWindow(files)

    win.show_modal()
    while win.is_shown():
        ix.application.check_for_events()

    return win.result
