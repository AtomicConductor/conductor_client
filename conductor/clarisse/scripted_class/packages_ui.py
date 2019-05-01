import ix
from conductor.clarisse.clarisse_info import ClarisseInfo
from conductor.clarisse.scripted_class import common
from conductor.native.lib import package_tree as pt
from conductor.native.lib.data_block import ConductorDataBlock

WINDOW_LEFT = 600
WINDOW_TOP = 200
WINDOW_HEIGHT = 600
WINDOW_WIDTH = 300
HALF_WIDTH = WINDOW_WIDTH / 2
BTN_HEIGHT = 20

C_LEFT = ix.api.GuiWidget.CONSTRAINT_LEFT
C_TOP = ix.api.GuiWidget.CONSTRAINT_TOP
C_RIGHT = ix.api.GuiWidget.CONSTRAINT_RIGHT
C_BOTTOM = ix.api.GuiWidget.CONSTRAINT_BOTTOM
C_COUNT = ix.api.GuiWidget.CONSTRAINT_COUNT


class PackageTreeItem(ix.api.GuiTreeItemBasic):
    """An item in the tree that maintains its own child list."""

    def __init__(self, parent, name):
        ix.api.GuiTreeItemBasic.__init__(self, parent, name)
        self.child_list = []
        self.was_selected = False


class PackageTreeWidget(ix.api.GuiTree):
    """Inherit from GuiTree to maintain our own child list.

    This implementation is way more complicated than it should be due to
    the fact that GuiTree#get_children() is buggy.
    See here:
    https://forum.isotropix.com/viewtopic.php?f=21&t=5391&p=19440#p19440

    I'm starting to think the idea of plugin packages belonging to host
    packages in a tree like fashion is incorrect.

    The only constraint should be that at most one version of each software
    can be chosen. There's no reason a customer can't have a Houdini session 
    with a renderman procedural that calls out to Maya in library mode to 
    provide geometry at rendertime.
    """

    def __init__(self, parent, x_val, y_val, width, height):
        ix.api.GuiTree.__init__(self, parent, x_val, y_val, width, height)
        self.set_border_style(ix.api.GuiTree.BORDER_STYLE_FLAT)
        self.set_shaded_entries(True)
        self.enable_multi_selection(True)
        self.set_constraints(C_LEFT, C_TOP, C_RIGHT, C_BOTTOM)
        self.child_list = []

        tree_data = ConductorDataBlock(product="clarisse").package_tree().tree

        self.root_item = self.get_root()
        self._build_ui(tree_data, self.root_item)

        self.connect(self, 'EVT_ID_TREE_SELECTION_CHANGED', self.on_selection)

    def clear(self):
        self._deselect_all(self)
        self._conform(self)

    def on_selection(self, sender, eventid):
        """Make sure only one item of each product is selected.

        For example, if user selects arnold 2.0, deselect arnold 3.0
        """
        old_selection = self._get_was_selected(self)
        new_selection = self._get_selected(self)

        # first, find the newly added
        added = list(set(new_selection) - set(old_selection))

        # make sure no repeats in added
        added = self._unique_product(added)

        added_products = [p.get_name().split(" ")[0] for p in added]

        # now remove unique added products from new_selection
        sel = self._remove_products(new_selection, added_products)

        self._deselect_all(self)

        to_select = sel + added
        for item in to_select:
            item.set_is_selected(True)

        # resolve
        self._conform(self)

    def _deselect_all(self, parent_item):
        """Deselect in UI."""
        for child in parent_item.child_list:
            child.set_is_selected(False)
            self._deselect_all(child)

    @staticmethod
    def _remove_products(items, products):
        """Make new list of items containing only those not in procucts.

        For example, if products contains arnold and clarisse, and items
        contains versions of yeti and clarisse, return yeti items. TODO:
        revisit this logic.
        """
        result = []
        for item in items:
            product = item.get_name().split(" ")[0]
            if product not in products:
                result.append(item)
        return result

    @staticmethod
    def _unique_product(items):
        """Find first item of some product.

        For example if if items contains 2 versions of arnold, get the
        first one. TODO, test more thoroughly to make sure this is
        correct logic!
        """
        seen_products = []
        result = []
        for item in items:
            product = item.get_name().split(" ")[0]
            if product not in seen_products:
                result.append(item)
                seen_products.append(product)
        return result

    def _get_selected(self, parent_item):
        """Recursively get the actual selected nodes."""
        result = []
        for child in parent_item.child_list:
            if child.is_selected():
                result.append(child)

            result += self._get_selected(child)
        return result

    def _get_was_selected(self, parent_item):
        """Recursively get the actual selected nodes."""
        result = []
        for child in parent_item.child_list:
            if child.was_selected:
                result.append(child)
            result += self._get_was_selected(child)
        return result

    def _conform(self, parent_item):
        """Make sure was_selected attr is the same as is_selected."""
        for child in parent_item.child_list:
            child.was_selected = child.is_selected()
            self._conform(child)

    def _build_ui(self, tree_data, parent_item):
        for child_tree in tree_data["children"]:
            name = str(pt.to_name(child_tree))
            child_tree_item = PackageTreeItem(parent_item, name)

            if parent_item == self.root_item:
                self.child_list.append(child_tree_item)
            else:
                parent_item.child_list.append(child_tree_item)

            self._build_ui(child_tree, child_tree_item)

        if tree_data["children"]:
            parent_item.set_expandable(True)
            parent_item.expand()

    def _select_leaf(self, parent_item, *nodes):
        try:
            children = parent_item.child_list
            child_item = next(c for c in children if c.get_name() == nodes[0])
        except StopIteration:
            return
        if len(nodes) == 1:
            child_item.set_is_selected(True)
            return
        self._select_leaf(child_item, *nodes[1:])

    def select_path_leaves(self, paths):
        for path in paths:
            nodes = path.split("/")
            self._select_leaf(self, *nodes)
        self._conform(self)


class PackageChooser(ix.api.GuiWindow):
    def __init__(self, node):
        ix.api.GuiWindow.__init__(
            self,
            ix.application.get_event_window(),
            WINDOW_LEFT,
            WINDOW_TOP,
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
            "Package chooser")
        self.set_resizable(False)
        self._build_top_row()
        self.node = node
        self.tree_widget = PackageTreeWidget(
            self,
            0,
            BTN_HEIGHT,
            WINDOW_WIDTH,
            WINDOW_HEIGHT - (BTN_HEIGHT * 2)
        )

        self._build_bottom_row()

    def _build_top_row(self):
        self.clear_but = ix.api.GuiPushButton(
            self, 0, 0, HALF_WIDTH, BTN_HEIGHT, "Clear")
        self.clear_but.set_constraints(C_LEFT, C_TOP, C_COUNT, C_TOP)
        self.connect(
            self.clear_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_clear_but)

        self.detect_but = ix.api.GuiPushButton(
            self,
            HALF_WIDTH,
            0,
            HALF_WIDTH,
            BTN_HEIGHT,
            "Detect")
        self.detect_but.set_constraints(C_COUNT, C_TOP, C_RIGHT, C_TOP)
        self.connect(
            self.detect_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_detect_but)

    def _build_bottom_row(self):
        self.cancel_but = ix.api.GuiPushButton(
            self,
            0,
            WINDOW_HEIGHT -
            BTN_HEIGHT,
            HALF_WIDTH,
            BTN_HEIGHT,
            "Cancel")
        self.cancel_but.set_constraints(C_LEFT, C_BOTTOM, C_COUNT, C_BOTTOM)
        self.connect(
            self.cancel_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_cancel_but)

        self.go_but = ix.api.GuiPushButton(
            self,
            150,
            WINDOW_HEIGHT -
            BTN_HEIGHT,
            HALF_WIDTH,
            BTN_HEIGHT,
            "Apply")
        self.go_but.set_constraints(C_COUNT, C_BOTTOM, C_RIGHT, C_BOTTOM)
        self.connect(self.go_but, 'EVT_ID_PUSH_BUTTON_CLICK', self.on_go_but)

    def on_clear_but(self, sender, eventid):
        self.tree_widget.clear()

    def on_detect_but(self, sender, eventid):
        """Select the current package if available in the list."""
        host = ClarisseInfo().get()
        paths = ConductorDataBlock(
            product="clarisse").package_tree().get_all_paths_to(
                **host)

        self.tree_widget.select_path_leaves(paths)

    def on_cancel_but(self, sender, eventid):
        self.hide()

    def _get_selected(self, item, selected_paths, path=None):
        """Dig down to get all selected itens."""
        for child in item.child_list:
            child_path = (
                "/").join([part for part in [path, child.get_name()] if part])
            if child.is_selected():
                selected_paths.append(child_path)
            self._get_selected(child, selected_paths, child_path)

    def on_go_but(self, sender, eventid):
        """Save the selected packages on the CobnductorJob node."""
        selected_items = []
        self._get_selected(self.tree_widget, selected_items)
        selected_items.sort(key=lambda item: item.count("/"))

        packages_att = self.node.get_attribute("packages")
        self.hide()

        packages_att.remove_all()
        for item in selected_items:
            packages_att.add_string(item)

        common.force_ae_refresh(self.node)


def build(*args):
    """Called from the attribute editor to build the window.

    Highlight any existing packages entries for the node.
    """
    node = args[0]
    window = PackageChooser(node)

    attr = node.get_attribute("packages")
    paths = ix.api.CoreStringArray()
    attr.get_values(paths)
    window.tree_widget.select_path_leaves(paths)

    window.show_modal()
    while window.is_shown():
        ix.application.check_for_events()
 
