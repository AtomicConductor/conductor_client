import ix
from conductor.clarisse.clarisse_info import ClarisseInfo
from conductor.clarisse.scripted_class import (frames_ui, instances_ui,
                                               projects_ui, variables, common)
from conductor.native.lib import package_tree as pt
from conductor.native.lib.data_block import ConductorDataBlock

C_LEFT = ix.api.GuiWidget.CONSTRAINT_LEFT
C_TOP = ix.api.GuiWidget.CONSTRAINT_TOP
C_RIGHT = ix.api.GuiWidget.CONSTRAINT_RIGHT
C_BOTTOM = ix.api.GuiWidget.CONSTRAINT_BOTTOM
C_COUNT = ix.api.GuiWidget.CONSTRAINT_COUNT


class PackageTreeItem(ix.api.GuiTreeItemBasic):
    def __init__(self, parent, name):
        ix.api.GuiTreeItemBasic.__init__(self, parent, name)
        self.child_list = []
        self.was_selected = False


class PackageTreeWidget(ix.api.GuiTree):

    def __init__(self, parent, x, y, w, h):
        ix.api.GuiTree.__init__(self, parent, x, y, w, h)
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

    def on_selection(self, sender, evtid):
        # stop listening to ensure we dont infinitely recurse
        # self.set_mute(True)

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
        print [n.get_name() for n in to_select]
        for item in to_select:
            item.set_is_selected(True)

        # resolve
        self._conform(self)

        # start listening again
        # self.set_mute(False)



    def _deselect_all(self, parent_item):
        for child in parent_item.child_list:
            child.set_is_selected(False)
            self._deselect_all(child)

    def _remove_products(self, items, products):
        """"""
        result = []
        for item in items:
            product = item.get_name().split(" ")[0]
            if product not in products:
                result.append(item)
        return result

    def _unique_product(self, items):
        """"""
        seen_products = []
        result = []
        for item in items:
            product = item.get_name().split(" ")[0]
            if product not in seen_products:
                seen_products.append(product)
                result.append(item)
        return result

    def _get_selected(self, parent_item):
        """Recursively get the actual selected nodes."""
        result = []
        for child in parent_item.child_list:
            if child.is_selected():
                result.append(child)

                # print child.get_name()
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
        # print "_select_leaf:" , parent_item
        try:
            children = parent_item.child_list
            print "N-0=", nodes[0],"  ", [c.get_name() for c in children]
            child_item = next(c for c in children if c.get_name() == nodes[0])
        except StopIteration:
            return
        if len(nodes) == 1:
            print "ADDING: ", child_item.get_name()
            child_item.set_is_selected(True)
            return
        self._select_leaf(child_item,  *nodes[1:])

    def select_path_leaves(self, paths):
        for path in paths:
            print "PROCESSING PATH: ", path
            nodes = path.split("/")
            # print nodes

            self._select_leaf(self, *nodes)
        self._conform(self)


class PackageChooser(ix.api.GuiWindow):
    WINDOW_LEFT = 600
    WINDOW_TOP = 200
    WINDOW_HEIGHT = 600
    WINDOW_WIDTH = 300
    HALF_WIDTH = WINDOW_WIDTH / 2
    BTN_HEIGHT = 20

    def __init__(self, node):
        ix.api.GuiWindow.__init__(
            self,
            ix.application.get_event_window(),
            PackageChooser.WINDOW_LEFT,
            PackageChooser.WINDOW_TOP,
            PackageChooser.WINDOW_WIDTH,
            PackageChooser.WINDOW_HEIGHT,
            "Package chooser")
        self.set_resizable(False)
        self._build_top_row()
        self.node = node
        self.tree_widget = PackageTreeWidget(
            self,
            0,
            PackageChooser.BTN_HEIGHT,
            PackageChooser.WINDOW_WIDTH,
            PackageChooser.WINDOW_HEIGHT - (PackageChooser.BTN_HEIGHT * 2)
        )

        self._build_bottom_row()

    def _build_top_row(self):
        self.clear_but = ix.api.GuiPushButton(
            self, 0, 0, PackageChooser.HALF_WIDTH, PackageChooser.BTN_HEIGHT, "Clear")
        self.clear_but.set_constraints(C_LEFT, C_TOP, C_COUNT, C_TOP)
        self.connect(
            self.clear_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_clear_but)

        self.detect_but = ix.api.GuiPushButton(
            self,
            PackageChooser.HALF_WIDTH,
            0,
            PackageChooser.HALF_WIDTH,
            PackageChooser.BTN_HEIGHT,
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
            PackageChooser.WINDOW_HEIGHT -
            PackageChooser.BTN_HEIGHT,
            PackageChooser.HALF_WIDTH,
            PackageChooser.BTN_HEIGHT,
            "Cancel")
        self.cancel_but.set_constraints(C_LEFT, C_BOTTOM, C_COUNT, C_BOTTOM)
        self.connect(
            self.cancel_but,
            'EVT_ID_PUSH_BUTTON_CLICK',
            self.on_cancel_but)

        self.go_but = ix.api.GuiPushButton(
            self,
            150,
            PackageChooser.WINDOW_HEIGHT -
            PackageChooser.BTN_HEIGHT,
            PackageChooser.HALF_WIDTH,
            PackageChooser.BTN_HEIGHT,
            "Apply")
        self.go_but.set_constraints(C_COUNT, C_BOTTOM, C_RIGHT, C_BOTTOM)
        self.connect(self.go_but, 'EVT_ID_PUSH_BUTTON_CLICK', self.on_go_but)

    def on_clear_but(self, sender, evtid):
        self.tree_widget.clear()

    def on_detect_but(self, sender, evtid):
        host = ClarisseInfo().get()
        paths = ConductorDataBlock(
            product="clarisse").package_tree().get_all_paths_to(
            **host)
 
        self.tree_widget.select_path_leaves(paths)

    def on_cancel_but(self, sender, evtid):
        self.hide()

    def _get_selected(self, item, selected_paths, path=None):
        for child in item.child_list:
            child_path = (
                "/").join([part for part in [path, child.get_name()] if part])
            if child.is_selected():
                selected_paths.append(child_path)
            self._get_selected(child, selected_paths, child_path)

    def on_go_but(self, sender, evtid):

        selected_items = []
        self._get_selected(self.tree_widget, selected_items)
        selected_items.sort(key=lambda item: item.count("/"))

        project_att = self.node.get_attribute("packages")
        self.hide()

        project_att.remove_all()
        for item in selected_items:
            project_att.add_string(item)

        common.force_ae_refresh(self.node)

def build(node, _):
    window = PackageChooser(node)


    attr = node.get_attribute("packages")
    paths = ix.api.CoreStringArray()
    attr.get_values(paths)
    window.tree_widget.select_path_leaves(paths)

    window.show_modal()
    while window.is_shown():
        ix.application.check_for_events()
    window.destroy()




