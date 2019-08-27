"""Provide a window in which to display a preview submission.

This is required because Clarisse's attribute editor doesn't allow
custom UI to be embedded.
"""


import json
import ix
import conductor.clarisse.utils as cu

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

SYMBOL_BUT_WIDTH = 30
CHECKBOX_WIDTH = 50

BOTTOM_BUT_WIDTH = WIDTH / 3


# def show_submission_responses(responses):
#     """Pop up an info dialog after submission.

#     The dialog is equipped to handle the results of an array of submissions.

#     """

#     success_jobs = [
#         response["response"]["uri"]
#         for response in responses
#         if response.get("code") == 201
#     ]

#     messages = []
#     if success_jobs:
#         success_msg = ", ".join(success_jobs)
#         messages.append("Successful submissions\n{}".format(success_msg))

#     num_failed = len([response for response in responses if response.get("code") > 201])

#     if num_failed:
#         messages.append("Number of failed submissions: {:d}".format(num_failed))

#     if messages:
#         msg = "\n".join(messages)
#     else:
#         msg = "No jobs were submitted"

#     ix.application.message_box(
#         msg,
#         "Conductor Submission: Info",
#         ix.api.AppDialog.yes(),
#         ix.api.AppDialog.STYLE_OK,
#     )


class MissingFilesWindow(ix.api.GuiWindow):
    """The entire window.

    Holds the panel plus buttons to Submit or Cancel.
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
        self.text_widget = ix.api.GuiTextEdit(self, 0, 0, WIDTH, HEIGHT)
        self.text_widget.set_constraints(C_LEFT, C_TOP, C_RIGHT, C_BOTTOM)
        self.text_widget.set_read_only(True)
        self.close_but = ix.api.GuiPushButton(
            self, 0, HEIGHT, BOTTOM_BUT_WIDTH, BTN_HEIGHT, "Close"
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
            "Submit",
        )
        self.go_but.set_constraints(C_RIGHT, C_BOTTOM, C_RIGHT, C_BOTTOM)
        # self.go_but.set_enable(can_submit)

        self.connect(self.go_but, "EVT_ID_PUSH_BUTTON_CLICK", self.on_go_but)

        self._populate()

    def _populate(self):
        """Put the submission args in the window."""

        content = "\n".join(self.files)
        self.text_widget.set_text(content)

    def on_close_but(self, sender, eventid):
        """Hide only.

        Don't destroy because hide will cause the event loop to end and
        destroy will kick in afterwards.
        """
        self.hide()

    def on_go_but(self, sender, eventid):
        """Set result and hide(destroy) the window."""
        self.result = True

        self.hide()


def proceed(files):
    """Show the window.

    Populate it with submission args for each job. Listen for events
    until the window is hidden.
    """
    if not files:
        return True
    win = MissingFilesWindow(files)

    win.show_modal()
    while win.is_shown():
        ix.application.check_for_events()

    return win.result
