from functools import wraps
from PySide import QtGui, QtCore, QtUiTools

class UiLoader(QtUiTools.QUiLoader):
    '''
    #TODO: Re-write docs/comments for this class

    Load a Qt Designer .ui file and returns an instance of the user interface.

    This was taken almost 100% verbatim from a stack overflow example.
    '''

    def __init__(self, baseinstance):
        super(UiLoader, self).__init__(baseinstance)
        self.baseinstance = baseinstance

    def createWidget(self, class_name, parent=None, name=''):
        if parent is None and self.baseinstance:
            # supposed to create the top-level widget, return the base instance
            # instead
            return self.baseinstance
        else:
            # create a new widget for child widgets
            widget = QtUiTools.QUiLoader.createWidget(self, class_name, parent, name)
            if self.baseinstance:
                # set an attribute for the new child widget on the base
                # instance, just like uic.loadUi does.
                setattr(self.baseinstance, name, widget)
            return widget

    @classmethod
    def loadUi(cls, uifile, baseinstance=None):
        '''
        Load a Qt Designer .ui file and returns an instance of the user interface.

        uifile: the file name or file-like object containing the .ui file.
        baseinstance: the optional instance of the Qt base class. If specified then the user interface is created in it. Otherwise a new instance of the base class is automatically created.
        Return type: the QWidget sub-class that implements the user interface.
        '''
        loader = cls(baseinstance)
        widget = loader.load(uifile)
        QtCore.QMetaObject.connectSlotsByName(widget)
        return widget


def wait_cursor(func):
    """
    Wraps the decorated function so that while it is running, the mouse
    cursor changes to waiting icon.
    """
    @wraps(func)
    def wrapper(*args, **kwds):
        try:
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            return func(*args, **kwds)
        finally:
            QtGui.QApplication.restoreOverrideCursor()
            # Not sure if this is needed
            QtGui.QApplication.processEvents()

    return wrapper



def wait_message(title, message):
    """
    Wraps the decorated method so that while it runs, a dialog box will
    be displayed with the given message and title
    """

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwds):
            parent = args[0]  # The first argument will be the wrapped method's class instance (i.e. self), which will be used as the parent
            dialog = QtGui.QDialog(parent=parent)
            layout = QtGui.QHBoxLayout()
            dialog.label = QtGui.QLabel()
            dialog.label.setText(message)
            dialog.label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
            layout.addWidget(dialog.label)
            dialog.setLayout(layout)
            dialog.setWindowTitle(title)
            dialog.show()
            # TODO: This stupid for-loop with a print statement is hack to force a redraw/update to the dialog. Otherwise it's blank. Tried a million things.  This is the only one that works..most of the time.
            for i in range(5):
                print "",
                QtGui.qApp.processEvents()
            try:
                return func(*args, **kwds)
            finally:
                dialog.done(0)
        return wrapper
    return decorator




def launch_message_box(title, message, is_richtext=False, parent=None):
    """
    Launches a very basic message dialog box with the given title and message. 
    
    is_richtext: bool. If True, willl set the given as RichText.  This will also
                 allow the text to support hyperlink behavior.
    """

    # create a QMessageBox
    dialog = QtGui.QMessageBox(parent=parent)

    # Set the window title to the given title string
    dialog.setWindowTitle(str(title))

    # Set the message text to the given message string
    dialog.setText(str(message))

    # Set the text to be selectable by a mouse
    text_label = dialog.findChild(QtGui.QLabel, "qt_msgbox_label")
    text_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    if is_richtext:
        text_label.setTextInteractionFlags(text_label.textInteractionFlags() | QtCore.Qt.TextBrowserInteraction)
        text_label.setTextFormat(QtCore.Qt.RichText)
        text_label.setOpenExternalLinks(True);

    return dialog.exec_()


def launch_error_box(title, message, parent=None):
    """
    Launches a QErrorMessage dialog box with the given title and message. 
    """

    # create a QErrorMessage
    dialog = QtGui.QErrorMessage(parent=parent)

    # Set the window title to the given title string
    dialog.setWindowTitle(str(title))

    # Set the message text to the given message string
    text_document = dialog.findChild(QtGui.QTextDocument)
    text_document.setPlainText(str(message))

    # find the icon (label) and hide it (it takes up too much space)
    label = dialog.findChild(QtGui.QLabel)
    label.hide()

    # find the checkbox and hide it (it serves no purpose for us)
    checkbox = dialog.findChild(QtGui.QCheckBox)
    checkbox.hide()
    return dialog.exec_()




class CheckBoxTreeWidget(QtGui.QTreeWidget):
    '''
    This is a QTreeWidget that has been modified to 
    '''

    # The column index od where the checkbox is located within a treewidgetitem
    checkbox_column_idx = 0

    icon_filepath_checked = ""
    icon_filepath_unchecked = ""
    icon_filepath_checked_disabled = ""
    icon_filepath_unchecked_disabled = ""

    def __init__(self, parent=None,):
        super(CheckBoxTreeWidget, self).__init__(parent=parent)
        self.checked_icon = QtGui.QIcon(self.icon_filepath_checked)
        self.unchecked_icon = QtGui.QIcon(self.icon_filepath_unchecked)
        self.initializeUi()



    def initializeUi(self):
        self.setCheckboxStyleSheet()


    def contextMenuEvent(self, event):
        selected_item = self.itemAt(event.pos())
        menu = self._make_context_menu(selected_item)
        menu.exec_(event.globalPos())



    def _make_context_menu(self, selected_item):
        menu = QtGui.QMenu()

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

        for item in [self.topLevelItem(idx) for idx  in range(self.topLevelItemCount())]:
            item.setCheckState(self.checkbox_column_idx, get_qt_check_flag(check))


    def _check_all_selected(self, check=True):
        '''
        Check or uncheck all of the checkboxes that are currently selected by the user
        '''

        for item in self.selectedItems():
            item.setCheckState(self.checkbox_column_idx, get_qt_check_flag(check))


    def addTopLevelCheckboxItem(self, tree_item, is_checked=False):
        '''
        Add the given QTreeWidgetItem as a top level widget and add a checkbox
        to it. 
        '''
        tree_item.setFlags(tree_item.flags() | QtCore.Qt.ItemIsUserCheckable)

        if is_checked:
            checked_state = QtCore.Qt.Checked
        else:
            checked_state = QtCore.Qt.Unchecked

        tree_item.setCheckState(self.checkbox_column_idx, checked_state)
        self.addTopLevelItem(tree_item)


    def setCheckboxStyleSheet(self):
        indicator_filepaths = {"QTreeWidget:indicator:unchecked": self.icon_filepath_unchecked,
                                "QTreeWidget:indicator:checked": self.icon_filepath_checked,
                                "QTreeWidget:indicator:checked:disabled": self.icon_filepath_checked_disabled,
                                "QTreeWidget:indicator:unchecked:disabled": self.icon_filepath_unchecked_disabled}
        stylesheet = ""

        for indicator, filepath in indicator_filepaths.iteritems():
            stylesheet += "%s { image: url(%s);}" % (indicator, filepath.replace("\\", "/"))  # The filepaths must always use forward slashes (regardless of platform)

        self.setStyleSheet(stylesheet)



def get_qt_check_flag(is_checked):
    if is_checked:
        return QtCore.Qt.Checked
    return QtCore.Qt.Unchecked

