"""Provide a window in which to add extra env vars.

This is required because Clarisse's attribute editor doesn't allow
custom UI to be embedded.
"""

import ix
import json
from conductor.clarisse.scripted_class import common


BTN_HEIGHT = 22
BTN_WIDTH = 100
WINDOW_LEFT = 600
WINDOW_TOP = 200
HEIGHT = 300
WIDTH = 900
PADDING = 5

SYMBOL_BUT_WIDTH = 30
CHECKBOX_WIDTH = 50

BOTTOM_BUT_WIDTH = WIDTH / 3
VAR_WDG_WIDTH = 300
VAL_WDG_WIDTH = WIDTH - \
    (SYMBOL_BUT_WIDTH + CHECKBOX_WIDTH + VAR_WDG_WIDTH + (PADDING * 5))


class VarWidget(ix.api.GuiWidget):
    """This is a line item containing UI for one env var.

    An env var has a merge policy (exclusive or append), so we have a
    checkbox for that. And we have a button to delete the line. We
    inherit because GuiWidget::get_child_items is broken and we have to
    have a way to store the children.
    """

    def __init__(self, parent, y, entry):
        super(
            VarWidget,
            self).__init__(
            parent,
            PADDING,
            y,
            WIDTH,
            BTN_HEIGHT)
        x = PADDING
        self.var_widget = ix.api.GuiLineEdit(
            self, x, y, VAR_WDG_WIDTH, BTN_HEIGHT)
        x += (VAR_WDG_WIDTH + PADDING)
        self.val_widget = ix.api.GuiLineEdit(
            self, x, y, VAL_WDG_WIDTH, BTN_HEIGHT)
        x += (VAL_WDG_WIDTH + PADDING)
        self.excl_cbx = ix.api.GuiCheckbox(
            self, x, y, "excl")
        x += (CHECKBOX_WIDTH + PADDING)
        self.delete_btn = ix.api.GuiPushButton(
            self, x, y, SYMBOL_BUT_WIDTH, BTN_HEIGHT, "X")

        self.var_widget.set_text(str(entry.get("key", "VARNAME")))
        self.val_widget.set_text(str(entry.get("value", "/some/value")))
        self.excl_cbx.set_value(bool(entry.get("excl", False)))
        self.show()

    # NOTE: maybe override destroy() so as to destroy children first. Lets see
    # if it crashes.

    def index(self):
        """Calculate the index of this widget in the list.

        Derive from it's height so we don't have to maintain another
        variable each time a line is added or deleted.
        """
        return (self.get_y() - PADDING - BTN_HEIGHT) / BTN_HEIGHT

    def set_y_index(self, index):
        """Adjust this widget's height based on its list position.

        Notice here we can't simply set the height of the container.
        Widgets locations are relative to the window, not their direct
        parent. In fact the only reason to set the parent's position is
        OCD.
        """
        y = ((index + 1) * BTN_HEIGHT) + PADDING
        self.set_position(self.get_x(), y)
        self.var_widget.set_position(self.var_widget.get_x(), y)
        self.val_widget.set_position(self.val_widget.get_x(), y)
        self.delete_btn.set_position(self.delete_btn.get_x(), y)

    def to_json(self):
        """Serialize for storage in the node's attribute."""
        return json.dumps({
            "key": self.var_widget.get_text(),
            "value": self.val_widget.get_text(),
            "excl": self.excl_cbx.get_value()

        }, sort_keys=True)


class EnvListWidget(ix.api.GuiPanel):
    """The panel within the window that provides scrollbars."""

    def __init__(self, parent, y):
        """Configure the panel and initialize an item_list.

        Since the GuiPanel::get_child_items is broken, we have to
        maintain our own list of children, and in fact this is the only
        reason for inheriting rather than using GuiPanel directly.
        """
        super(EnvListWidget, self).__init__(parent, 0, y, WIDTH, HEIGHT)
        self.set_scroll_enabled(True)
        self.set_bottom_toolbar_visible(False)
        self.set_top_toolbar_visible(False)
        self.item_list = []

    def _items_height(self):
        """Calculate the total height of items.

        Need this in order to add new items at the bottom, and to tell
        the scollable area how big the virtual space is.
        """
        return PADDING + ((len(self.item_list) + 1) * BTN_HEIGHT)

    def add_entries(self, *entries):
        """Add a line and hook up the delete button event."""
        num_existing = len(self.item_list)

        for entry in entries:
            y = self._items_height()
            wdg = VarWidget(self, y, entry)
            self.item_list.append(wdg)
            self.connect(
                wdg.delete_btn,
                "EVT_ID_PUSH_BUTTON_CLICK",
                self.on_remove_but)

        self.set_virtual_size(self.get_width(), self._items_height())

    def on_remove_but(self, sender, evtid):
        """Remove from view.

        We have to keep the item_list in sync.
        """
        p = sender.get_parent()
        i = p.index()
        p.hide()
        p.destroy()
        self.item_list.pop(i)
        self._arrange_items()

    def _arrange_items(self, **kw):
        for i, item in enumerate(self.item_list):
            item.set_y_index(i)


class EnvWindow(ix.api.GuiWindow):
    """The entire window.

    Holds the panel plus buttons to Add, Go, Cancel and so on.
    """

    def __init__(self, node):
        self.node = node
        window_height = HEIGHT + (BTN_HEIGHT * 2)

        super(EnvWindow, self).__init__(ix.application.get_event_window(),
                                        WINDOW_LEFT,
                                        WINDOW_TOP,
                                        WIDTH,
                                        window_height,
                                        "Extra environment")

        current_y = 0
        self.add_but = ix.api.GuiPushButton(
            self, (WIDTH - BTN_WIDTH), current_y, BTN_WIDTH, BTN_HEIGHT, "Add")
        self.connect(self.add_but, "EVT_ID_PUSH_BUTTON_CLICK", self.on_add_but)

        current_y += BTN_HEIGHT
        self.panel = EnvListWidget(self, BTN_HEIGHT)
        current_y += HEIGHT

        self.close_but = ix.api.GuiPushButton(
            self, 0, current_y, BOTTOM_BUT_WIDTH, BTN_HEIGHT, "Close")
        self.connect(
            self.close_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_close_but)

        self.apply_but = ix.api.GuiPushButton(
            self,
            BOTTOM_BUT_WIDTH,
            current_y,
            BOTTOM_BUT_WIDTH,
            BTN_HEIGHT,
            "Apply")
        self.connect(
            self.apply_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_apply_but)

        self.go_but = ix.api.GuiPushButton(
            self,
            (WIDTH - BOTTOM_BUT_WIDTH),
            current_y,
            BOTTOM_BUT_WIDTH,
            BTN_HEIGHT,
            "Go")
        self.connect(self.go_but, 'EVT_ID_PUSH_BUTTON_CLICK', self.on_go_but)

    def on_add_but(self, sender, evtid):
        self.panel.add_entries({})

    def on_close_but(self, sender, evtid):
        """Hide only.

        Don't destroy because hide will cause the event loop to end and
        destroy will kick in afterwards.
        """
        self.hide()

    def on_apply_but(self, sender, evtid):
        """Save values on the attribute and keep the window visible."""
        self._apply()

    def on_go_but(self, sender, evtid):
        """Save values on the attribute and hide(destroy) the window."""
        self._apply()
        self.hide()

    def _apply(self):
        """The real work of saving values on the attribute."""
        attr = self.node.get_attribute("extra_environment")
        attr.remove_all()
        for item in self.panel.item_list:
            attr.add_string(item.to_json())
        common.force_ae_refresh(self.node)


def build(node, _):
    """Show the window.

    Populate it with existing entries from the extra_env attribute. The
    window is shown in modal mode so we don't keep losing the damn thing
    behind other stuff. Listen for events until the window is hidden.
    """
    win = EnvWindow(node)

    attr = node.get_attribute("extra_environment")
    json_entries = ix.api.CoreStringArray()
    attr.get_values(json_entries)
    entries = [json.loads(entry) for entry in json_entries]
    if not entries:
        entries = [{}]
    win.panel.add_entries(*entries)

    win.show_modal()
    while win.is_shown():
        ix.application.check_for_events()
    # Need to test. Sometimes I get a crash after using this UI and then
    # killing with the OS close button. I suspect it destroys the window 
    # immediately, but then it gets destroyed again after the event loop ends.
    # If that's the case, i'll uncomment the line below.
    # if not win.is_destroyed():
    win.destroy()
