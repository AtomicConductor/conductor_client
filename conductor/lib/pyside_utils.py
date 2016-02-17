import logging
from functools import wraps
from PySide import QtGui, QtCore, QtUiTools


logger = logging.getLogger(__name__)

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



def get_widgets_by_property(widget, property_name, match_value=False, property_value=None):
    '''
    For the given widget, return all child widgets (and potentially the original widget),
    which have a property of the given property_name.  
    Optionally, return only those widgets whose given property matches the given
    property_value 
    '''
    widgets = []
    for widget_ in widget.findChildren(QtGui.QWidget):
        if property_name in widget_.dynamicPropertyNames():
            # If we're not matching against the property value, or if the property value is of the given value, then use it
            if not match_value or widget_.property(property_name) == property_value:
                widgets.append(widget_)
    return widgets


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



class UiUserSettings(object):
    '''
    Facilitates the saving and loading of user preferences (from and to disk),
    and the application of those settings to the UI.  The idea is that the UI can
    have it's state recorded, and then be restored to that state at a later point. 

    Settings are recorded per context, where a context is the currently opened 
    maya/katana/nuke/etc file. So every file that's opened in maya (or whateve), 
    can have settings recorded for it. 
    
    In Qt lingo the context is called a "group" (in QSettings).  We name the group
    using the filepath for the currently opened maya/katana/nuke/etc file. 
    All groups of settings are written to the same preference file (the file can 
    hold many groups).
    
    Because this class must read widget values and write those values to a text 
    file and conversely, read those values from a text file and apply them back
    to the widgets, there needs to be binding/mapping of getters/setters so
    that different widget types can properly read/set the values from/to the
    preferences file.
    '''

    # Random unlikely character combination to escape special characters with
    encoder = "^||^"


    @classmethod
    def loadUserSettings(cls, company_name, application_name, group_name, widgets):
        '''
        Load user settings for the given group that are found in the qt prefs file. 
        The prefs file is located/created via the company_name and application_name.
               
        company_name: str. Dictates the subdirecty directory name of where the 
                      settings file is found on disk
                      
        application_name: str. Dictates the name of the settings file (excluding
                               directory path)
                  
        group_name: str.  The group name for which to load the settings for. This
                          can be anything you want.  Just remember what it was
                          so that you can use it to restore setting later.    
        
        widgets: list of Qt Widget objects to have settings loaded for.
        '''
        qsettings = QtCore.QSettings(company_name, application_name)

        logger.debug("Loading settings for: %s", group_name)
        group_name = cls.encodeGroupName(group_name)

        qsettings.beginGroup(group_name)
        for widget_name in qsettings.childKeys():
            widget_value = qsettings.value(widget_name)
            if widget_value != None:
                cls.restoreWidgetValue(widget_name, widget_value, widgets)
        qsettings.endGroup()

    @classmethod
    def saveUserSettings(cls, company_name, application_name, group_name, widgets):
        '''
        Save user settings for the given group to the qt prefs file. 
        The prefs file is located/created via the company_name and application_name.
               
        company_name: str. Dictates the subdirecty directory name of where the 
                      settings file is saved to disk
                      
        application_name: str. Dictates the name of the settings file (excluding
                               directory path)
                  
        group_name: str.  The group name for which to save the settings for. This
                          can be anything you want.  Just remember what it was
                          so that you can use it to restore setting later.    
        
        widgets: list of Qt Widget objects to have settings save for.
        '''
        qsettings = QtCore.QSettings(company_name, application_name)
        logger.debug("Saving settings for: %s", group_name)
        group_name = cls.encodeGroupName(group_name)
        qsettings.beginGroup(group_name)

        for widget in widgets:
            widget_name = widget.objectName()
            widget_value = cls.getWidgetValue(widget)
            qsettings.setValue(widget_name, widget_value)

        qsettings.endGroup()

        logger.debug("User settings written to: %s" % qsettings.fileName())

    @classmethod
    def encodeGroupName(cls, group_name):
        '''
        Unfortunately qsettings uses the "/" as a special character to indicate
        nested keys in a group name.  We happen to want to use forward slashes
        in our keys to express filepath, so we swap out the forward slash with
        different set of characters (i.e. "encode" the "/" to something else)
        '''
        return group_name.replace("/", cls.encoder)

    @classmethod
    def getWidgetValue(cls, widget):
        '''
        Return the value for the given widget object.  Because a widget can be
        of any class, and every widget class has different methods for retrieving
        its values, this function uses a mapping of different getter functions
        for each widget type.  More widget types may need to be added to this 
        mapping in the future.
        '''
        widget_type = type(widget)
        getter_map = {QtGui.QLineEdit: cls.getLineEditValue,
                      QtGui.QComboBox: cls.getComboBoxValue,
                      QtGui.QCheckBox: cls.getCheckboxValue,
                      QtGui.QSpinBox: cls.getSpinboxValue,
                      QtGui.QRadioButton: cls.getRadioButtonValue}


        getter_func = getter_map.get(widget_type)
        if not getter_func:
            raise Exception("No getter function mapped for widget class: %s", widget_type)
        return getter_func(widget)

    @classmethod
    def restoreWidgetValue(cls, widget_name, widget_value, widgets):
        '''
        
        Set the given value on the widget of the given name.  Because a widget can be
        of any class, and every widget class has different methods for setting
        its values, this function uses a mapping of different setter functions
        for each widget type.  More widget types may need to be added to this 
        mapping in the future.
        
        
        widget_name: the name of the widget, e.g. QWidget.objectName()
        widget_value: the value to set the widget to. This value comes from
                      the settings file.
        
        '''


        setter_map = {QtGui.QLineEdit: cls.setLineEditValue,
                      QtGui.QComboBox: cls.setComboBoxValue,
                      QtGui.QCheckBox: cls.setCheckboxValue,
                      QtGui.QSpinBox: cls.setSpinboxValue,
                      QtGui.QRadioButton: cls.setRadioButtonValue}

        widget = cls.getWidgetByName(widget_name, widgets)
        widget_type = type(widget)

        setter_func = setter_map.get(widget_type)
        if not setter_func:
            raise Exception("No setter function mapped for widget class: %s", widget_type)
        return setter_func(widget, widget_value)

    @classmethod
    def getWidgetByName(cls, widget_name, widgets):
        '''
        From the given list of widget objects, return the widget object that has
        the given widget name.  Raise an exception if it cannot be found
        '''
        for widget in widgets:
            if widget.objectName() == widget_name:
                return widget
        raise Exception("Expected widget %s not found: %s" % widget_name)

    @classmethod
    def getLineEditValue(cls, lineedit):
        '''
        Define getter function for QLineEdit widgets
        '''
        return str(lineedit.text())

    @classmethod
    def setLineEditValue(cls, lineedit, value):
        '''
        Define setter function for QLineEdit widgets
        '''
        # Ensure that value is cast to a string first
        lineedit.setText(str(value))

    @classmethod
    def getComboBoxValue(cls, combobox):
        '''
        Define getter function for QComobobox widgets
        '''
        return combobox.currentIndex()

    @classmethod
    def setComboBoxValue(cls, combobox, value):
        '''
        Define setter function for QComobobox widgets
        '''
        # Ensure that value is cast to an int first
        combobox.setCurrentIndex(int(value))

    @classmethod
    def getRadioButtonValue(cls, radiobutton):
        '''
        Define getter function for QRadioButton widgets
        '''
        return radiobutton.isChecked()

    @classmethod
    def setRadioButtonValue(cls, radiobutton, value):
        '''
        Define setter function for QRadioButton widgets.
        Since the value comes from qsettings (which casts bools to strings and 
        lowercase), we  have to do a little processing.
        '''
        value_lower = value.lower()

        if value_lower == "false":
            value = False
        elif value_lower == "true":
            value = True
        else:
            raise Exception("Got unexpected radiobutton value: %s", value)

        radiobutton.setChecked(value)

    @classmethod
    def getCheckboxValue(cls, checkbox):
        '''
        Define getter function for QCheckbox widgets
        '''
        return checkbox.isChecked()

    @classmethod
    def setCheckboxValue(cls, checkbox, value):
        '''
        Define setter function for QCheckbox widgets
        Since the value comes from qsettings (which casts bools to strings and 
        lowercase), we  have to do a little processing.
        '''
        value_lower = value.lower()

        if value_lower == "false":
            value = False
        elif value_lower == "true":
            value = True
        else:
            raise Exception("Got unexpected checkbox value: %s", value)

        checkbox.setChecked(value)

    @classmethod
    def setSpinboxValue(cls, spinbox, value):
        '''
        Define setter function for QSpinBox widgets
        '''

        spinbox.setValue(int(value))

    @classmethod
    def getSpinboxValue(cls, spinbox):
        '''
        Define getter function for QSpinBox widgets
        '''
        return spinbox.value()




