import collections
import functools
import json
import os
import random
import sys

import dateutil.parser
import datetime

from Qt import QtGui, QtCore, QtWidgets
from qtpy import uic
import qtmodern.styles
import qtmodern.windows

from conductor.lib import pyside_utils, file_utils, common, exceptions, package_utils
from conductor.desktop.lib import module
# from . import RESOURCES_DIRPATH

RESOURCES_DIRPATH = os.path.join(os.path.dirname(__file__), "resources")


# override_paint = 0  # 0 or 1 or 2
#
#
# class TestDelegate(QtGui.QStyledItemDelegate):
#
#     def paint(self, painter, option, index):
#         super(TestDelegate, self).paint(painter, option, index)
#
#
# app = QtGui.QApplication(sys.argv)
#
# # Make tableview
# tableView = QtGui.QTableView()
# tableView.setStyleSheet("""QTableView::item { padding: 10px;
#                                                background-color: blue;
#                                               }""")
#
# # Make delegate
# delegate = TestDelegate(tableView)
# tableView.setItemDelegate(delegate)
#
# # Make the model
# model = QtGui.QStandardItemModel(4, 2)
# for row in range(4):
#     for column in range(2):
#         index = model.index(row, column, QtCore.QModelIndex())
#         model.setData(index, "\n".join(["(%i, %i)" % (row, column)]))
# tableView.setModel(model)
#
# tableView.show()
# sys.exit(app.exec_())
#
#
#
# void SomeItemDelegate::paint(QPainter *painter,
#                               const QStyleOptionViewItem &option,
#                               const QModelIndex &index) const
# {
#     QLabel renderer;
#     renderer.setStyleSheet(getStyleSheet(index));
#     renderer.setText(makeDisplayString(index));
#     renderer.resize(option.rect.size());
#     painter->save();
#     painter->translate(option.rect.topLeft());
#     renderer.render(painter);
#     painter->restore();
# }

class PersistentMenu(QtWidgets.QMenu):
    '''
    A QMenu that stays open after having an action selected/checked.
    '''

    def mouseReleaseEvent(self, *args, **kwargs):
        '''
        Override to prevent menu from hiding/closing after checkbox is checked/unchecked
        '''
        action = self.activeAction()
        if action:
            action.trigger()


class DownloaderModule(module.DesktopModule):
    _ui_filepath = os.path.join(RESOURCES_DIRPATH, 'downloader.ui')

    def __init__(self, parent=None):
        super(DownloaderModule, self).__init__(parent=parent)
        uic.loadUi(self._ui_filepath, self)
        pyside_utils.apply_style_file(self, os.path.join(RESOURCES_DIRPATH, "style.qss"), append=True)
        self.jobs_trwgt = DownloaderTreeWidget()
        self.ui_shell_wgt.layout().addWidget(self.jobs_trwgt)
        jobs_data = self.getJobs()
        self.jobs_trwgt.populate(jobs_data)
        self.columns_menu = self.createColumnsMenu()
        self.applyColumnPrefs()

    def createColumnsMenu(self):
        menu = PersistentMenu()
        for column_name in self.jobs_trwgt.resource_map:
            action = menu.addAction(column_name)
            action.setCheckable(True)
            action.toggled.connect(functools.partial(self.jobs_trwgt.setColumnVisibility, column_name))

        self.ui_columns_tbtn.setMenu(menu)
        return menu

    def getColumnPrefs(self):
        '''
        '''

#         return (
#             ("Job", {"is_hidden": False}),
#             ("Date", {"is_hidden": False}),
#             ("Project", {"is_hidden": False}),
#             ("Owner", {"is_hidden": False}),
#             ("Title", {"is_hidden": False}),
#             ("Tasks", {"is_hidden": False}),
#             ("Progress", {"is_hidden": False}),
#             ("Download Directory", {"is_hidden": False}),
#             ("Location", {"is_hidden": True}),
#         )

        return {
            "Job": {"is_visible": True},
            "Date": {"is_visible": True},
            "Project": {"is_visible": True},
            "Owner": {"is_visible": True},
            "Title": {"is_visible": True},
            "Tasks": {"is_visible": True},
            "Progress": {"is_visible": True},
            "Download Directory": {"is_visible": True},
            "Location": {"is_visible": False},
        }

    def applyColumnPrefs(self):
        '''
        Show/hide columns based upon the user's prefs.  Also sync the columns menu checkboxes to the
        corresponding state.
        '''
        actions_by_text = dict([(action.text(), action) for action in self.columns_menu.actions()])
        for column_name, column_prefs in self.getColumnPrefs().items():
            action = actions_by_text[column_name]
            is_visible = column_prefs.get("is_visible", True)
            action.setChecked(is_visible)
            self.jobs_trwgt.setColumnVisibility(column_name, is_visible)

    def getNavbarVisible(self):
        return True

    def getNavbarName(self):
        return "Downloader"

    def getJobs(self):
        with open(os.path.join(RESOURCES_DIRPATH, 'jobs.json')) as f:
            return json.load(f)["data"]


class ResourceTreeWidget(QtWidgets.QTreeWidget):

    def __init__(self, parent=None):
        self.resource_map = self.getColumnResourceMapping()
        self.columns_index = dict([column_name, index] for index, column_name in enumerate(self.resource_map.keys()))
        print ("self.columns_index", self.columns_index)
        super(ResourceTreeWidget, self).__init__(parent=parent)
        self.setIndentation(0)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setHeaderItem(QtWidgets.QTreeWidgetItem(list(self.resource_map.keys())))
        self.setSortingEnabled(True)
#         self.setFocusPolicy(QtCore.Qt.NoFocus)

    def contextMenuEvent(self, event):
        selected_item = self.itemAt(event.pos())
        menu = self._make_context_menu(selected_item)
        menu.exec_(event.globalPos())

    def _make_context_menu(self, selected_item):
        menu = QtWidgets.QMenu()

        # "check selected" menu item
        action = menu.addAction(self.checked_icon, "check selected",
                                lambda check=True: self._check_all_selected(check))
        action.setIconVisibleInMenu(True)

        # "uncheck selected" menu item
        action = menu.addAction(self.unchecked_icon, "uncheck selected",
                                lambda check=False: self._check_all_selected(check))
        action.setIconVisibleInMenu(True)

        menu.addSeparator()

        # "check all" menu item
        action = menu.addAction(self.checked_icon, "check all",
                                lambda check=True: self._check_all(check))
        action.setIconVisibleInMenu(True)

        # "uncheck all" menu item
        action = menu.addAction(self.unchecked_icon, "uncheck all",
                                lambda check=False: self._check_all(check))
        action.setIconVisibleInMenu(True)

        return menu

    def _check_all(self, check=True):
        '''
        Check or uncheck all of the checkboxes
        '''

        for item in [self.topLevelItem(idx) for idx in range(self.topLevelItemCount())]:
            item.setCheckState(self.checkbox_column_idx, get_qt_check_flag(check))

    def _check_all_selected(self, check=True):
        '''
        Check or uncheck all of the checkboxes that are currently selected by the user
        '''

        for item in self.selectedItems():
            item.setCheckState(self.checkbox_column_idx, get_qt_check_flag(check))

    def populate(self, jobs_data):
        '''
        Populate each render layer into the UI QTreeWidget.
        If the render layer has been set to renderable in maya, then check its
        qtreewidgetitem's checkbox (on) the the render layer  UI.  Only render
        layers that are checked on will be rendered
        '''
        self.clear()

        for job_data in jobs_data:
            item = JobItem(self.orderResourceData(job_data))

#             row_data = [job_data.get(data_map.get(column_name), "") for column_name in self.getColumnNames()]
#             tree_item = QtWidgets.QTreeWidgetItem(row_data)
            font = item.font(0)
            font.setPointSize(15)
            item.setFont(0, font)
#             print ("item.font.size", item.font(0).pointSize())
#             item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)

            self.addTopLevelItem(item)

        self.resizeColumnToContents(0)
        print ("style2", self.styleSheet())

    def getColumnResourceMapping(self):
        '''
        Return the mapping between a column name and a resource field.  This mapping also dictates
        column order (via an ordered dictionary).
        '''
        mapping = collections.OrderedDict((
            ("Job", "jid"),
            ("Date", "time_created"),
            ("Project", "project"),
            ("Owner", "owner"),
            ("Title", "title"),
            ("Tasks", "task_keys"),
            ("Progress", None),
            ("Download Directory", "output_path"),
            ("Location", "location"),
        ))

        return mapping

    def orderResourceData(self, resource_data):
        '''
        For the given resource data (resource json dict), return an OrderedDict where the v
        '''
        ordered_data = collections.OrderedDict()
        for column_name, field_name in self.resource_map.items():
            ordered_data[column_name] = resource_data.get(field_name)
        return ordered_data

    def setColumnVisibility(self, column_name, is_visible):
        index = self.columns_index[column_name]
        self.setColumnHidden(index, not is_visible)


class DownloaderTreeWidget(ResourceTreeWidget):

    def populate(self, jobs_data):
        '''
        '''
        column_idx = list(self.resource_map.keys()).index("Progress")
        super(DownloaderTreeWidget, self).populate(jobs_data)
        print ("self.topLevelItemCount()", self.topLevelItemCount())
        for item in [self.topLevelItem(idx) for idx in range(self.topLevelItemCount())]:
            progress_bar = QtWidgets.QProgressBar()
            progress_bar = QtWidgets.QProgressBar(self)
            progress_bar.setMinimum(0)
            print ("item._data", item._data)
            progress_bar.setMaximum(len(item._data["Tasks"]))
            progress_bar.setValue(random.randint(0, len(item._data["Tasks"])))
            self.setItemWidget(item, column_idx, progress_bar)

        self.resizeColumnToContents(0)


class ResourceItem(QtWidgets.QTreeWidgetItem):
    '''
    This class represents a REST resource as a QTreeWidgetItem. It describes how to transform
    a json representation of a resource into a QTreeWidgetItem. This may include:
        - 
    This class introduces the notion of mapping a field/column name to a column idx. (A QTreeWidgetItem
    typically identifies a column by a column index (not a key value), i.e as a list rather than a dict.

    resource_data

    resource_schema
        - name
        - type



    '''

    def __init__(self, resource_data, parent=None):
        '''
        resource_data: OrderedDict e.g. list of two-item tuples, where each tuple represents a column/cell of data. 
            The order of the items in the list will dictate the displayed column order.
            [
                ("Job": "30202"),
                ("Task": "001"),
                ("Account": "20000202"),
            ]

        '''
        print("resource_data", resource_data)
        self.validateData(resource_data)
        self._data = resource_data
        self._column_indices = dict()
        super(ResourceItem, self).__init__(parent=parent)
        for column_idx, field_data in enumerate(self._data.items()):
            field_name, field_value = field_data
            value = self.transformResourceValue(field_name, field_value)
            self.setData(column_idx, QtCore.Qt.DisplayRole, value)

    def validateData(self, resource_data):
        '''
        Validate that 
        1. the data structure consists of a list of two-item tuples (str, any)
        2. the same column name isn't used more than once
        '''

    def transformResourceValue(self, column_name, column_value, role=QtCore.Qt.DisplayRole):
        '''
        Qt::DisplayRole    0    The key data to be rendered in the form of text. (QString)
        '''
        getter_method_name = "transformResource{}Value".format(column_name.capitalize())

        getter_method = getattr(self, getter_method_name, None)
        print ("getter_method_name", getter_method_name, getter_method)
        return getter_method(column_value, role) if getter_method else column_value

#     def deriveDecorationValue(self, column_name):
#         '''
#         Qt::DecorationRole    1    The data to be rendered as a decoration in the form of an icon. (QColor, QIcon or QPixmap)
#         '''
#
#     def deriveEditValue(self, column_name):
#         '''
#         Qt::EditRole    2    The data in a form suitable for editing in an editor. (QString)
#         '''
#
#     def deriveToolTipValue(self, column_name):
#         '''
#         Qt::ToolTipRole    3    The data displayed in the item's tooltip. (QString)
#         '''
#
#     def deriveStatusTipValue(self, column_name):
#         '''
#         Qt::StatusTipRole    4    The data displayed in the status bar. (QString)
#         '''
#
#     def deriveWhatsThisValue(self, column_name):
#         '''
#         Qt::WhatsThisRole    5    The data displayed for the item in "What's This?" mode. (QString)
#         '''
#
#     def deriveSizeHintValue(self, column_name):
#         '''
#         Qt::SizeHintRole    13    The size hint for the item that will be supplied to views. (QSize)
#         '''

    def deriveRoleData(self, column_name, role):
        pass

    @staticmethod
    def humanTimestamp(date_time):
        '''
        as_tz: dateutil.tz.tzutc, dateutil.tz.tzlocal
        '''
        # convert datetime to epoch time (force/assume the datetime we've received is utc)
        epoch_time = date_time.replace(tzinfo=datetime.timezone.utc).timestamp()

        # Get the datetime string format for the current locale
        locale = QtCore.QLocale()
        datetime_format = locale.dateTimeFormat(QtCore.QLocale.ShortFormat)

        return QtCore.QDateTime.fromSecsSinceEpoch(epoch_time).toString(datetime_format)


#
#     @staticmethod
#     def human_cost(cost, ljust=0, rjust=0):
#         return ("%.2f" % cost).ljust(ljust).rjust(rjust)
#
#     @staticmethod
#     def human_duration(seconds, ljust=0, rjust=0):
#         return str(datetime.timedelta(seconds=round(seconds))).ljust(ljust).rjust(rjust)


#     def __lt__(self, otherItem):
#         column = self.treeWidget().sortColumn()
#         return self.text(column).toLower() < otherItem.text(column).toLower()


class JobItem(ResourceItem):

    def __init__(self, resource_data, parent=None):
        '''
        resource_data: OrderedDict e.g. list of two-item tuples, where each tuple represents a column/cell of data. 
            The order of the items in the list will dictate the displayed column order.
            [
                ("Job": "30202"),
                ("Task": "001"),
                ("Account": "20000202"),
            ]

        '''
        print("resource_data", resource_data)
        self.validateData(resource_data)
        self._data = resource_data
        super(ResourceItem, self).__init__(parent=parent)
        for column_idx, field_data in enumerate(self._data.items()):
            field_name, field_value = field_data
            value = self.transformResourceValue(field_name, field_value)
            self.setData(column_idx, QtCore.Qt.DisplayRole, value)

    def transformResourceProjectValue(self, value, role):
        if value:
            return value.split("|")[-1]

    def transformResourceTasksValue(self, value, role):
        if value:
            return len(value)

    def transformResourceDateValue(self, value, role):
        if value:
            date_time = dateutil.parser.parse(value)
            return self.humanTimestamp(date_time)

#
# if __name__ == '__main__':
#     app = QtWidgets.QApplication(sys.argv)
#     qtmodern.styles.dark(app)
#     dialog_1 = Dialog_01()
#     dialog_1.show()
#     dialog_1.resize(480, 320)
#     sys.exit(app.exec_())


if __name__ == "__main__":
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseStyleSheetPropagationInWidgetStyles)
    app = QtWidgets.QApplication(sys.argv)
    downloader = DownloaderModule()
    pyside_utils.apply_style_file(app, "/home/lschlosser/git/conductor_client_desktop/conductor/desktop/resources/style.qss")

    ### DEFAULT STYLING ###
#     downloader.show()

    ### QTMODERN STYLING ###
    qtmodern.styles.dark(app)
    mw = qtmodern.windows.ModernWindow(downloader)
    mw.show()
    mw.windowHandle().setScreen(app.screens()[0])

    sys.exit(app.exec_())

# if __name__ == "__main__":
#
#     app = QtWidgets.QApplication(sys.argv)
#     widget = QtWidgets.QWidget()
# #     w.windowHandle().setScreen(app.screens()[1])
#     widget.show()
# #     window = widget.windowHandle()
# #     print ("widget", widget)
# #     print ("window", window)
# #     print ("positopn", window.position())
# #     print ("framePosition", window.framePosition())
#
#     sys.exit(app.exec_())
