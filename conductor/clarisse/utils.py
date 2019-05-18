import ix
from contextlib import contextmanager


@contextmanager
def waiting_cursor():
    clarisse_win = ix.application.get_event_window()
    old_cursor = clarisse_win.get_mouse_cursor()
    clarisse_win.set_mouse_cursor(ix.api.Gui.MOUSE_CURSOR_WAIT)
    yield
    clarisse_win.set_mouse_cursor(old_cursor)

@contextmanager
def disabled_app():
    app = ix.application
    app.disable()
    yield
    app.enable()
