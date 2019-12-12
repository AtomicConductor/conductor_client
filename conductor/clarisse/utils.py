"""
Contexts for performing long or delicate functions.
"""
import os
from contextlib import contextmanager

import ix


@contextmanager
def waiting_cursor():
    """
    Perform some function with the wait cursor showing.
    """
    clarisse_win = ix.application.get_event_window()
    old_cursor = clarisse_win.get_mouse_cursor()
    clarisse_win.set_mouse_cursor(ix.api.Gui.MOUSE_CURSOR_WAIT)
    yield
    clarisse_win.set_mouse_cursor(old_cursor)


@contextmanager
def disabled_app():
    """
    Disble the app to perform some function.
    """
    app = ix.application
    app.disable()
    yield
    app.enable()


def is_windows():
    return os.name == "nt"
