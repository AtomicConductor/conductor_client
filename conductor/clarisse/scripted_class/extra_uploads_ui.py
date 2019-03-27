import ix
from conductor.clarisse.scripted_class import common
from conductor.native.lib.dependency_list import DependencyList

BTN_HEIGHT = 22
BTN_WIDTH = 100
WINDOW_LEFT = 600
WINDOW_TOP = 200
HEIGHT = 300
WIDTH = 900


class FileListWidget(ix.api.GuiTree):
    """Build a list of files using a tree widget.

    Use the tree widget because its the only way to get multiselect in
    clarisse.
    """

    def __init__(self, parent, y):
        """Set up the tree config.

        We inherit so that we can keep a list of children, due to
        GuiWidget,get_child_items being broken.
        """
        ix.api.GuiTree.__init__(self, parent, 0, y, WIDTH, HEIGHT)
        self.set_border_style(ix.api.GuiTree.BORDER_STYLE_FLAT)
        self.set_shaded_entries(True)
        self.enable_multi_selection(True)
        self.enable_item_delete(True)
        self.item_list = []

    def add_entries(self, entries):
        """Add a line item for each entry.

        Use DependencyList to deduplicate on the fly. As the addition of
        entries may completely change the list (grow or shrink) we
        delete and rebuild the list of entries each time.
        """
        if not entries:
            return

        root_item = self.get_root()

        deduped = DependencyList()
        for item in self.item_list:
            # no need to stat as we must have once already
            deduped.add(item.get_name(), must_exist=False)

        for entry in entries:
            deduped.add(entry)
        # clear existing list
        root_item.remove_children()
        del self.item_list[:]

        for entry in deduped:
            item = ix.api.GuiTreeItemBasic(root_item, entry)
            self.item_list.append(item)
        self.refresh()

    def destroy_selelcted(self):
        """Remove the selected items.

        Also remove from the item_list.
        """
        indices = self._get_selected_indices()
        if not indices:
            ix.log_warning("Nothing selected")
            return
        self.destroy_selected_items()
        self.refresh()
        self._remove_entries_from_sync_item_list(indices)

    def destroy_all(self):
        """Clear all items."""
        self.get_root().remove_children()
        del self.item_list[:]
        self.refresh()

    def _get_selected_indices(self):
        """Get indices.

        Get in reverse order so they don't change during removal.
        """
        indices = sorted([i for i, item in enumerate(
            self.item_list) if item.is_selected()])
        indices.reverse()
        return indices

    def _remove_entries_from_sync_item_list(self, indices):
        for index in indices:
            self.item_list.pop(index)


class ExtraUploadsWindow(ix.api.GuiWindow):
    """Window to contain the tree.

    It has buttons to browse and manage the list. It also has regular
    apply, go, close buttons at the bottom.
    """

    def __init__(self, node):

        self.node = node

        window_height = HEIGHT + (BTN_HEIGHT * 2)
        ix.api.GuiWindow.__init__(
            self,
            ix.application.get_event_window(),
            WINDOW_LEFT,
            WINDOW_TOP,
            WIDTH,
            window_height,
            "Extra uploads")
        self.set_resizable(False)

        current_y = 0
        self.browse_but = ix.api.GuiPushButton(
            self, (WIDTH - BTN_WIDTH), current_y,
            BTN_WIDTH, BTN_HEIGHT, "Browse")
        self.connect(
            self.browse_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_browse_but)

        self.remove_sel_but = ix.api.GuiPushButton(
            self, 0, current_y, BTN_WIDTH, BTN_HEIGHT, "Remove selected")
        self.connect(
            self.remove_sel_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_remove_sel_but)

        self.remove_all_but = ix.api.GuiPushButton(
            self, BTN_WIDTH, current_y, BTN_WIDTH, BTN_HEIGHT, "Remove all")
        self.connect(
            self.remove_all_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_remove_all_but)

        current_y += BTN_HEIGHT
        self.file_list_wdg = FileListWidget(self, current_y)
        current_y += HEIGHT

        go_btn_width = int(WIDTH / 3)

        self.close_but = ix.api.GuiPushButton(
            self, 0, current_y, go_btn_width, BTN_HEIGHT, "Close")
        self.connect(
            self.close_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_close_but)

        self.apply_but = ix.api.GuiPushButton(
            self, go_btn_width, current_y, go_btn_width, BTN_HEIGHT, "Apply")
        self.connect(
            self.apply_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_apply_but)

        self.go_but = ix.api.GuiPushButton(
            self,
            (WIDTH - go_btn_width),
            current_y,
            go_btn_width,
            BTN_HEIGHT,
            "Go")
        self.connect(self.go_but, 'EVT_ID_PUSH_BUTTON_CLICK', self.on_go_but)

    def on_browse_but(self, sender, evtid):
        """User may browse for files."""
        app = ix.application
        title = "Select extra uploads..."
        mask = "Any files\t*"
        filenames = ix.api.GuiWidget.open_files(app, "", title, mask)

        self.file_list_wdg.add_entries(filenames)

    def on_remove_sel_but(self, sender, evtid):
        self.file_list_wdg.destroy_selelcted()

    def on_remove_all_but(self, sender, evtid):
        self.file_list_wdg.destroy_all()

    def on_close_but(self, sender, evtid):
        """Hide the widget.

        Destruction will be be triggered as the event loop ends.
        """
        self.hide()

    def on_apply_but(self, sender, evtid):
        self._apply()

    def on_go_but(self, sender, evtid):
        self._apply()
        self.hide()

    def _apply(self):
        """Save this list of files on the node.

        Force the AE to update afterwards.
        """
        attr = self.node.get_attribute("extra_uploads")
        attr.remove_all()
        for item in self.file_list_wdg.item_list:
            attr.add_string(item.get_name())
        common.force_ae_refresh(self.node)


def build(node, _):
    """Pop up a window to choose extra upload files."""
    win = ExtraUploadsWindow(node)
    win.show_modal()

    attr = node.get_attribute("extra_uploads")
    paths = ix.api.CoreStringArray()
    attr.get_values(paths)
    win.file_list_wdg.add_entries(paths)

    while win.is_shown():
        ix.application.check_for_events()

    # win.destroy is recommended but makes Clarisse crash
    # when saving the scene
    # win.destroy()
