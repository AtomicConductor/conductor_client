from collections import defaultdict
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

    # expand the dailog box a little larger if needed
    dialog.adjustSize()
    return dialog.exec_()


def launch_yes_no_dialog(title, message, show_not_agin_checkbox=True, parent=None):
    '''
    Launch a dialog box that has "yes" and "no" buttons.  
    Optionally display a checkbox that asks whether to show this dialog box again.
    return the result of this dialog (True/False) and whether the user checked on
    the "Don't ask again" checkbox (True/False).
    '''

    dialog = QtGui.QDialog(parent=parent)
    dialog.setWindowTitle(title)
    dialog.verticalLayout = QtGui.QVBoxLayout(dialog)

    # Create the dialogs main message (Qlabel)
    dialog.label = QtGui.QLabel(dialog)
    dialog.label.setAlignment(QtCore.Qt.AlignCenter)
    dialog.label.setTextInteractionFlags(dialog.label.textInteractionFlags() | QtCore.Qt.TextBrowserInteraction)
    dialog.label.setTextFormat(QtCore.Qt.RichText)
    dialog.label.setOpenExternalLinks(True);
    dialog.label.setText(message)
    dialog.verticalLayout.addWidget(dialog.label)


    dialog.widget = QtGui.QWidget(dialog)
    dialog.horizontalLayout = QtGui.QHBoxLayout(dialog.widget)
    dialog.horizontalLayout.setContentsMargins(-1, -1, -1, 0)
    dialog.horizontalLayout.setObjectName("horizontalLayout")
    dialog.verticalLayout.addWidget(dialog.widget)

    # Create the "Don\t ask again" checkbox
    dialog.checkBox = QtGui.QCheckBox(dialog.widget)
    dialog.checkBox.setText("Don\'t ask again")
    dialog.horizontalLayout.addWidget(dialog.checkBox)

    # Create the buttonbox with "yes" and "no buttons"
    dialog.buttonBox = QtGui.QDialogButtonBox(dialog.widget)
    dialog.buttonBox.setOrientation(QtCore.Qt.Horizontal)
    dialog.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.No | QtGui.QDialogButtonBox.Yes)
    dialog.horizontalLayout.addWidget(dialog.buttonBox)
    # Connect the buttonbox signals
    QtCore.QObject.connect(dialog.buttonBox, QtCore.SIGNAL("accepted()"), dialog.accept)
    QtCore.QObject.connect(dialog.buttonBox, QtCore.SIGNAL("rejected()"), dialog.reject)
    QtCore.QMetaObject.connectSlotsByName(dialog)

    # Hide the checkbox if not desired
    if not show_not_agin_checkbox:
        dialog.checkBox.hide()

    # Resize the dialog box to scale to its contents
    dialog.adjustSize()

    # Launch the dialog
    yes = dialog.exec_()
    dont_notify_again = dialog.checkBox.isChecked()
    return bool(yes), dont_notify_again



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


def get_top_level_items(tree_widget):
    '''
    For the given QTreeWidget, return all top level QTreeItems
    '''

    return [tree_widget.topLevelItem(idx) for idx in range(tree_widget.topLevelItemCount())]

def get_all_tree_items(tree_widget):
    '''
    For the given QTreeWidget, return all of its QTreeWidgetItems.  This is
    an exhaustive, recursive search, capturing all top level as well as child
    QTreeWidgetItems.
    '''
    all_items = []
    for tree_item in get_top_level_items(tree_widget):
        all_items.extend(_get_child_tree_items(tree_item))
    return all_items


def _get_child_tree_items(tree_widget_item):
    ''' 
    For the given QTreeWidgetItem, recursively seek out and return all child 
    QTreeWidgetItems
    '''
    nodes = []
    nodes.append(tree_widget_item)
    for i in range(tree_widget_item.childCount()):
        nodes.extend(_get_child_tree_items(tree_widget_item.child(i)))
    return nodes


class WidgetGettrSettr(object):
    '''
    Provides  getter/setter functionality for QWidgets, making it easier to read/load
    widget values.  This is particularly useful when needing to record a widget's
    value for user preferences, and conversely, reapplying those settings back
    to the widget.
    
    Every widget type must be mapped to a getter and setter method.
    
    '''

    @classmethod
    def getGettrMap(cls):
        '''
        Return a dictionary mapping of "getter" functions that provide a mapping
        between a Widget type and a function that can read a value from that
        widget type (i.e. read a human entered value from the widget).
        
        This dictionary should be expanded as needed, when other widget types
        are required for reading/loading data to/from. 
        '''
        return {QtGui.QLineEdit: cls.getLineeditValue,
                QtGui.QComboBox: cls.getComboBoxValue,
                QtGui.QCheckBox: cls.getCheckBoxValue,
                QtGui.QSpinBox: cls.getSpinboxValue,
                QtGui.QRadioButton: cls.getRadioButtonValue}

    @classmethod
    def getSettrMap(cls):
        '''
        Return a dictionary mapping of "setter" functions that provide a mapping
        between a Widget type and a function that can write a value to that
        widget type (i.e populat the widget with that value).
        
        This dictionary should be expanded as needed, when other widget types
        are required for reading/loading data to/from. 
        '''
        return {QtGui.QLineEdit: cls.setLineEditValue,
                QtGui.QComboBox: cls.setComboBoxValue,
                QtGui.QCheckBox: cls.setCheckBoxValue,
                QtGui.QSpinBox: cls.setSpinboxValue,
                QtGui.QRadioButton: cls.setRadioButtonValue}


    @classmethod
    def getWidgetValue(cls, widget):
        '''
        Return the value for the given widget object.  Because a widget can be
        of any class, and every widget class has different methods for retrieving
        its values, this function uses a mapping of different getter functions
        for each widget type.  More widget types may need to be added to this 
        mapping in the future.
        '''
        # Determine the widget type
        widget_type = type(widget)

        # Attempt to find a gettr function for the widget type
        getter_func = cls.getGettrMap().get(widget_type)
        if not getter_func:
            raise Exception("No getter function mapped for widget class: %s", widget_type)

        logger.debug("Querying value from widget: %s", widget.objectName())
        # Call the the gettr function
        return getter_func(widget)


    @classmethod
    def setWidgetValue(cls, widget, widget_value):
        '''
        
        Set the given value on the widget object  Because a widget can be
        of any class, and every widget class has different methods for setting
        its values, this function uses a mapping of different setter functions
        for each widget type. see cls.getGettrMap
        
        widget: QWidget derivative (must have a getter/setter mapping in cls.getSettrMap)
        widget_value: the value to populate the widget with.
        '''
        # Determine the widget type
        widget_type = type(widget)

        # Attempt to find a settr function for the widget type
        setter_func = cls.getSettrMap().get(widget_type)
        if not setter_func:
            raise Exception("No setter function mapped for widget class: %s", widget_type)
        logger.debug("Applying pref to widget %s: %s", widget.objectName(), widget_value)
        # Call the the settr function
        return setter_func(widget, widget_value)


    @classmethod
    def getLineeditValue(cls, lineedit):
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
        Store the text in the combobox (rather than the current index).  This
        allows the ordering of the items to change while maintaining the correct
        preference behavior
        '''
        return combobox.currentText()

    @classmethod
    def setComboBoxValue(cls, combobox, value):
        '''
        Define setter function for QComobobox widgets
        
        Find the given text value in the combobox items.  If no items contain
        the text, the index will be set to -1 (blank).  This makes sense, as
        it will tell the user that their preference value is no longer valid, and
        to select something different. 
        '''
        # Ensure that value is cast to an int first
        entry_idx = combobox.findText(value)
        combobox.setCurrentIndex(entry_idx)

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
        radiobutton.setChecked(value)

    @classmethod
    def getCheckBoxValue(cls, checkbox):
        '''
        Define getter function for QCheckbox widgets
        '''
        return checkbox.isChecked()

    @classmethod
    def setCheckBoxValue(cls, checkbox, value):
        '''
        Define setter function for QCheckbox widgets
        Since the value comes from qsettings (which casts bools to strings and 
        lowercase), we  have to do a little processing.
        '''
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



class UserPrefs(object):
    '''
    Base level helper-class to faciliate saving/loading user preferences to/from
    disk.
    '''

    # Random unlikely character combination to escape special characters with. This is unfortunate/hacky.
    ENCODER = "^||^"

    def __init__(self, company_name, application_name):
        '''
        Create a user settings file for the given company and application name 
        The prefs file is located/created via the company_name and application_name.
               
        company_name: str. Dictates the subdirecty directory name of where the 
                      settings file is found on disk
                      
        application_name: str. Dictates the name of the settings file (excluding
                               directory path)
        '''
        self.company_name = company_name
        self.application_name = application_name
        self.qsettings = QtCore.QSettings(company_name, application_name)


    #### GETTERS #####

    def getSettingsFilepath(self):
        '''
        Return the filepath to the QSettings file
        '''
        return self.qsettings.fileName()

    def getValue(self, key, group=None, cast_bools=True):
        '''
        Return the value for the given key. If a group is given, search the group
        for the key and return its value.
        
        key: str. The name of the preference to return a value for.
        group: str. The preference group/namespace to search for the preference.
               If not specified, will use the default/root namespace
        cast_bools: bool.  Cast any "true" or "false" values to python bools
        '''
        logger.debug("Reading setting: %s/%s", group or "ROOT", key)
        if group:
            self.qsettings.beginGroup(group)
        value = self.qsettings.value(key)
        if group:
            self.qsettings.endGroup()

        if cast_bools:
            return self.castToBool(value)

        return value

    def getValues(self, group=None, cast_bools=True):
        '''
        Return all preference values found in the given preference group. If no
        a preference group is specified, use the default/root preference group.
        Return a dictionary, where the key is the preference name, and the value
        is the preference value.
        
        key: str. The name of the preference to return a value for.
        group: str. The preference group/namespace to search for the preference.
               If not specified, will use the default/root namespace
        cast_bools: bool.  Cast any "true" or "false" values to python bools
        '''
        group_values = {}
        logger.debug("Reading group settings: %s/", group or "ROOT")
        if group:
            self.qsettings.beginGroup(group)
        for key in self.qsettings.childKeys():
            value = self.qsettings.value(key)
            if cast_bools:
                value = self.castToBool(value)
            group_values[key] = value
        if group:
            self.qsettings.endGroup()
        return group_values

    def setValue(self, key, value, group=None):
        '''
        Set the value for the given preference in the given preference group.
        If no preference group is specified, set the value in the default/root 
        preference group.
          
        Note that if a python bool is given as a value, QSettings automatically 
        converts this to a lowercase string version of it ("false", "true").
        
        key: str. The name of the preference to set a value for.
        value: str, bool.  The value to set the preferece to.
        group: str. The preference group/namespace to set the preference for
               If not specified, will use the default/root namespace
        
        '''
        logger.debug("Writing setting: %s/%s", group or "ROOT", key)
        if group:
            self.qsettings.beginGroup(group)
        value = self.qsettings.setValue(key, value)
        if group:
            self.qsettings.endGroup()
        self.qsettings.sync()
        return value

    def setValues(self, values, group=None):
        '''
        Set the given preference values in the given preference group. If no
        a preference group is specified, use the default/root preference group.
        Return a dictionary, where the key is the preference name, and the value
        is the preference value.
        
        key: str. The name of the preference to return a value for.
        group: str. The preference group/namespace to search for the preference.
               If not specified, will use the default/root namespace
        cast_bools: bool.  Cast any "true" or "false" values to python bools
        '''
        logger.debug("Writing group settings: %s/", group or "ROOT")
        if group:
            self.qsettings.beginGroup(group)
        for key, value in values.iteritems():
            self.qsettings.setValue(key, value)
        self.qsettings.sync()
        if group:
            self.qsettings.endGroup()


    @classmethod
    def castToBool(cls, value):
        '''
        Cast the given value to a bool (if it's considered a "bool" type). 
        '''
        if value == "false":
            value = False
        elif value == "true":
            value = True
        return value


    @classmethod
    def encodeGroupName(cls, group_name):
        '''
        Unfortunately qsettings uses the "/" as a special character to indicate
        nested keys in a group name.  We may  want to use forward slashes
        in our keys (such as a filepath), so we swap out the forward slash with
        different set of characters (i.e. "encode" the "/" to something else)
        '''
        if not group_name:
            return group_name
        return group_name.replace("/", cls.ENCODER)

    def sync(self):
        '''
        A convenience method to QSetting's synch method.  Syncs pref data from memory
        to disk and visa versa.  This doesn't *have* to be called, but QT doesn't
        write the settings to disk *everytime* a change is made...so this is a
        way to ensure that it does at critical moments.  
        '''
        self.qsettings.sync()

    def clear(self):
        '''
        A convenience method to QSetting's clear method. Deletes preferences
        '''
        self.qsettings.clear()


    def clearGroup(self, group):
        '''
        Clear all keys/values from given group
        '''
        logger.debug("Clearing group: %s", group)
        self.qsettings.beginGroup(group)
        self.qsettings.remove("")
        self.qsettings.endGroup()



class FilePrefs(UserPrefs):
    '''
    This class facilicates the saving/loading of user preferences from/to disk
    while providing a structured scope to save that preference to.  A scope is
    either global or file-specific.  Scopes are achieved by using QtSettings'
    "groups" (i.e. namespaces).  All scopes of settings are written to the same 
    preference file.  An example use-case for these scopes is when a user
    wants preferences to be saved for a particular file that they have opened at
    the moment.  Or a user might want preferences to be applied regardless of
    what file is opened at the moment.
    '''
    ### PREFERENCE GROUPS (namespaces) ####

    # Group for storeing global preferences
    GROUP_GLOBAL_PREFS = "global/prefs"

    # Group for storeing file-specific preferences
    GROUP_FILE_PREFS = "file/prefs"



    ##########################
    # ALL PREFS METHODS
    ##########################

    #### GETTERS #####

    def getPref(self, pref_name, filepath=None):
        '''
        High level convenence function that will return the preference value
        for either a global or file-specific preference.
        
        pref_name: str. the name of the preference to return a value for, e.g. "frame_range"
        filepath: str. The name of the file to return the preference value for.
                  If the filepath is not provided, then the global preference will
                  be searched for.        
        '''
        if filepath:
            return self.getFilePref(filepath, pref_name)
        return self.getGlobalPref(pref_name)


    def getPrefs(self, filepath=None):
        '''
        High level convenence function that will return a dictionary of either
        file-specific preferences
        
        filepath: str. The name of the file to return the preference values for.
                  If the filepath is not provided, then the global preferences will
                  be returned.  
        '''
        if filepath:
            return self.getFilePrefs(self, filepath)

        return self.getGlobalPrefs()


    #### SETTERS #####

    def setPref(self, pref_name, value, filepath=None):
        '''
        High level convenence function that will set the preference value
        for either a global or file-specific preference.
        
        pref_name: str. the name of the preference to set a value for, e.g. "frame_range"
        
        value: the value to save for the preference, e.g. "1001-1040"
        
        filepath: str. The name of the file to set the preference value for.
                  If the filepath is not provided, then a global preference will
                  be set.       
        '''
        if filepath:
            return self.setFilePref(filepath, pref_name, value)
        return self.setGlobalPref(pref_name, value)


    def setPrefs(self, values, filepath=None):
        '''
        High level convenence function that will set the given preference values
        for either global or file-specific scope.
        
        pref_name: str. the name of the preference to return a value for, e.g. "frame_range"
        
        values: dict. key=preference name, value=preference value
        
        filepath: str. The name of the file to set the preference values for.
                  If the filepath is not provided, then the values will be set
                  for the global prefs.        
        '''
        if filepath:
            return self.setFilePrefs(filepath, values)
        return self.setGlobalPrefs(values)




    ##########################
    # GLOBAL PREFS METHODS
    ##########################

    #### GETTERS #####

    def getGlobalPref(self, pref_name):
        '''
        Return the value for given global preference
        
        pref_name: the name of the preference to return a value for, e.g. "frame_range"
        '''
        return self.getValue(pref_name, group=self.GROUP_GLOBAL_PREFS)

    def getGlobalPrefs(self):
        '''
        Return a dictionary of all global preferences
        '''
        return self.getValues(self.GROUP_GLOBAL_PREFS)


    #### SETTERS #####

    def setGlobalPref(self, pref_name, value):
        '''
        Set the value for given global preference
        
        pref_name: the name of the preference to return a value for, e.g. "frame_range"
        '''
        self.setValue(pref_name, value, group=self.GROUP_GLOBAL_PREFS)

    def setGlobalPrefs(self, values):
        '''
        Set the the given values to the global preferences
        
        values: dict. key=preference name, value=preference value
        '''
        self.setValues(values, self.GROUP_GLOBAL_PREFS)


    ##########################
    # FILE PREFS
    ##########################


    #### GETTERS #####

    def getFilePref(self, filepath, pref_name):
        '''
        Return the user preferences for the given preference for the given file 
        '''
        group = self.GROUP_FILE_PREFS + "/" + self.encodeGroupName(filepath)
        return self.getValue(pref_name, group)

    def getFilePrefs(self, filepath):
        '''
        Return a dictionary of all user preferences for the given file 
        '''
        group = self.GROUP_FILE_PREFS + "/" + self.encodeGroupName(filepath)
        return self.getValues(group)


    #### SETTERS #####

    def setFilePref(self, filepath, pref_name, value):
        '''
        Set the given preference to the given value for the given file
        
        pref_name: the name of the preference to set a value for, e.g. "frame_range"
        value: the value to save for the preference, e.g. "1001-1040"
        '''
        group = self.GROUP_FILE_PREFS + "/" + self.encodeGroupName(filepath)
        self.setValue(pref_name, value, group)

    def setFilePrefs(self, filepath, values):
        '''
        Set the the given preference values for the given file
        
        values: dict. key=preference name, value=preference value
        '''
        group = self.GROUP_FILE_PREFS + "/" + self.encodeGroupName(filepath)
        self.setValues(values, group=group)



    #### CLEAR PREFS ####

    # Clear GLOBAL prefs
    def clearGlobalPrefs(self):
        '''
        Clear all of the preferencs found in the global group/namespace
        '''
        self.clearGroup(self.GROUP_GLOBAL_PREFS)

    # Clear GLOBAL prefs
    def clearFilePrefs(self, filepath):
        '''
        Clear all of the preferencs found in the given filepath's group/namespace
        '''
        group = self.GROUP_FILE_PREFS + "/" + self.encodeGroupName(filepath)
        self.clearGroup(group)



class UiFilePrefs(FilePrefs):
    '''
    Extends the parent class to allow the state of the UI's widget to be recorded, 
    and then restored at a later point. 

    Because this class must read widget values and write those values to a text 
    file and conversely, read those values from a text file and apply them back
    to the widgets, there needs to be binding/mapping of getters/setters so
    that different widget types can properly read/set the values from/to the
    preferences file.  This binding class must be provided upon instantiation.
    
    This class adds two more scopes (groups) to it's parent classes':
        
        - "global/widgets"   # Group for storing global widget preferences
        - "file/widgets"     # Group for storing file-specific widget preferences
  
    '''


    ### PREFERENCE GROUPS/NAMESPACES ####

    # Group for storing global widget preferences
    GROUP_GLOBAL_WIDGETS = "global/widgets"

    # Group for storing file-specifi widget preferences
    GROUP_FILE_WIDGETS = "file/widgets"

    # a mapping class for reading/writing to QWidget object
    widget_mapper = WidgetGettrSettr


    def __init__(self, company_name, application_name, file_widgets=(), global_widgets=()):
        '''
        company_name: str. Dictates the subdirecty directory name of where the 
                      settings file is found on disk
                      
        application_name: str. Dictates the name of the settings file (excluding
                               directory path)
        
        
        file_widgets: list of Qt Widget objects to have settings saved/loaded for, 
                      for EACH SCENE FILE that is opened.
        global_widgets: list of Qt Widget objects to have settings saved/loaded for to
                       be applied GLOBALLY (across all scene files) 
        '''
        self._file_widgets = file_widgets
        self._global_widgets = global_widgets
        super(UiFilePrefs, self).__init__(company_name, application_name)



    ##########################
    # HIGH LEVEL METHODS
    ##########################

    def getPref(self, pref_name, filepath=None, is_widget=False):
        '''
        High level convenence function that returns the value for the given 
        preference name. If a filepath is given, return  the preference stored 
        for that specific file, otherwise return the global value.  
        
        pref_name: str. The name of the preference, such as "Dont_bug_me",
        
        filepath: str. The name of the file to return the preference value for.
        
        is_widget: bool. Indicates that the pref_name is widget_name.
        
        return: The value of the preference, e.g "yes", "no", "true", "false"
        
        '''
        if is_widget:
            if filepath:
                return self.getFileWidgetPref(filepath, widget_name=pref_name)
            return self.getGlobalWidgetPref(widget_name=pref_name)

        return super(UiFilePrefs, self).getPref(pref_name, filepath=filepath)


    def getPrefs(self, filepath=None, is_widget=False):
        '''
        High level convenence function that will return a dictionary of either
        file-specific preferences or global preferences.
        
        filepath: str. The name of the file to return the preference values for.
                  If the filepath is not provided, then the global preferences will
                  be returned.  
        
        filepath: str. The name of the file to return the preference value for.
        
        is_widget: bool. Indicates that the pref_name is widget_name.
        
        return: dict.  values of the preferences.
        
        '''
        if is_widget:
            if filepath:
                return self.getFileWidgetPrefs(filepath)
            return self.getGlobalWidgetPrefs()

        return super(UiFilePrefs, self).getPrefs(filepath=filepath)



    #### SETTERS #####

    def setPref(self, pref_name, value, filepath=None, is_widget=False):
        '''
        High level convenence function that will set the preference value
        for either a global preference or  file-specific preference.
        
        pref_name: str. the name of the preference to set a value for, e.g. "frame_range"
        
        value: the value to save for the preference, e.g. "1001-1040"
        
        filepath: str. The name of the file to set the preference value for.
                  If the filepath is not provided, then a global preference will
                  be set.       
        '''
        if is_widget:
            if filepath:
                return self.setFileWidgetPref(filepath, widget_name=pref_name, value=value)
            return self.setGlobalWidgetPref(widget_name=pref_name, value=value)

        return super(UiFilePrefs, self).setPref(pref_name, value, filepath=filepath)

    def setPrefs(self, values, filepath=None, is_widget=False):
        '''
        High level convenence function that will set the given preference values
        for either the global scope or a file-specific scope.
        
        values: dict. key=preference name, value=preference value
        
        filepath: str. The name of the file to set the preference values for.
                  If the filepath is not provided, then the values will be set
                  for the global prefs. 
       is_widget: bool. Indicates whether the preference if for a QWidget or not.       
        '''

        # If the preference is for a widget, save it to the widget pref scrope
        if is_widget:
            # If a filepath is provided, set the preference as a file-specfic pref.
            if filepath:
                return self.setFileWidgetPrefs(filepath, values)
            return self.setGlobalWidgetPrefs(values)

        # Otherwise save the pref normally (using the parent method)
        return super(UiFilePrefs, self).setPrefs(values, filepath=filepath)


    #### SAVE WIDGET PREFERENCES

    def saveFileWidgetPrefs(self, filepath):
        '''
        Save widget settings for the given file. 
        '''
        logger.debug("Saving user widget prefs for: %s", filepath)
        self._saveWidgetPrefs(self._file_widgets, filepath=filepath)

    def saveGlobalWidgetPrefs(self):
        '''
        Save user widgt settings to the global prefs
        '''
        logger.debug("Saving global widget prefs")
        self._saveWidgetPrefs(self._global_widgets)

    def _saveWidgetPrefs(self, widgets, filepath=None):
        '''
        Save all user widget prefs.  If a filepath is provided, save the prefs
        as file-specfic 
        '''
        widget_prefs = {}

        for widget in widgets:
            widget_name = widget.objectName()
            widget_value = self.widget_mapper.getWidgetValue(widget)
            widget_prefs[widget_name] = widget_value

        if filepath:
            self.setFileWidgetPrefs(filepath, widget_prefs)
        else:
            self.setGlobalWidgetPrefs(widget_prefs)



    ##### LOAD WIDGET PREFERENCES

    def loadFileWidgetPrefs(self, filepath):
        '''
        Load/apply any user prefs for the given file (read from the qt prefs file). 
        The prefs file is located/created via the company_name and application_name.
        
        filepath: str. Filpath for the currently opened file to load widget
                       preferences for.
        '''

        logger.debug("Loading User Widget prefs for file: %s", filepath)
        for widget_name, widget_value in self.getFileWidgetPrefs(filepath).iteritems():
            if widget_value != None:
                widget = self.getWidgetByName(widget_name)
                self.widget_mapper.setWidgetValue(widget, widget_value)

    def loadGlobalWidgetPrefs(self):
        '''
        Load/apply any global user prefs. 
        '''
        logger.debug("Loading User Global Widget prefs")
        for widget_name, widget_value in self.getGlobalWidgetPrefs().iteritems():
            if widget_value != None:
                widget = self.getWidgetByName(widget_name)
                self.widget_mapper.setWidgetValue(widget, widget_value)



    ##########################
    # GLOBAL PREFS
    ##########################

    #### GETTERS #####


    def getGlobalWidgetPref(self, widget_name):
        '''
        Return the global preference value for the given widget name
        
        widget_name: the name of the widget object, e.g. "ui_frames_lnedt"
        '''
        return self.getValue(widget_name, group=self.GROUP_GLOBAL_WIDGETS)

    def getGlobalWidgetPrefs(self):
        '''
        Return the all global widget preferences 
        '''
        return self.getValues(self.GROUP_GLOBAL_WIDGETS)


    #### SETTERS #####

    def setGlobalWidgetPref(self, widget_name, value):
        '''
        Record the given value for the given widget (name) to the global preferences
        
        widget_name: the name of the widget object, e.g. "ui_frames_lnedt"
        value: the value to record for the widget, .e.g "1001x2"
        '''
        self.setValue(widget_name, value, group=self.GROUP_GLOBAL_WIDGETS)


    def setGlobalWidgetPrefs(self, widget_values):
        '''
        Record the given widget values to the global preferences
        
        widget_values: dict. key=widget name, value=widget value
        '''
        self.setValues(widget_values, self.GROUP_GLOBAL_WIDGETS)



    ##########################
    # FILE PREFS
    ##########################


    #### GETTERS #####

    def getFileWidgetPref(self, filepath, widget_name):
        '''
        Return the preference for the given widget name for the given file 
        
        filepath: str. The filepath to get preferences for
        widget_name: the name of the widget object, e.g. "ui_frames_lnedt"
        '''
        group = self.GROUP_FILE_WIDGETS + "/" + self.encodeGroupName(filepath)
        return self.getValue(widget_name, group)

    def getFileWidgetPrefs(self, filepath):
        '''
        Return all widget preferences for the given file 
        
        filepath: str. The filepath to get preferences for
        
        '''
        group = self.GROUP_FILE_WIDGETS + "/" + self.encodeGroupName(filepath)
        return self.getValues(group)



    #### SETTERS #####

    def setFileWidgetPref(self, filepath, widget_name, value):
        '''
        Record the given value for the given widget (name) for the given filepath.

        filepath: str. The filepath to save preferences for
        widget_name: the name of the widget object, e.g. "ui_frames_lnedt"
        value: the value to record for the widget, .e.g "1001x2"
        '''
        group = self.GROUP_FILE_WIDGETS + "/" + self.encodeGroupName(filepath)
        self.setValue(widget_name, value, group)


    def setFileWidgetPrefs(self, filepath, widget_values):
        '''
        Record the given widget values for the given filepath
        
        widget_values: dict. key=widget name, value=widget value
        '''
        group = self.GROUP_FILE_WIDGETS + "/" + self.encodeGroupName(filepath)
        self.setValues(widget_values, group)


    def getWidgetByName(self, widget_name):
        '''
        Return the widget object that has the given widget object name.  
        Raise an exception if it cannot be found.  Only widgets that have been
        provided upon this class's instantiation will be searched.
        '''
        all_widgets = list(self._global_widgets) + list(self._file_widgets)
        for widget in all_widgets:
            if widget.objectName() == widget_name:
                return widget
        raise Exception("Expected widget not found: %s" % widget_name)



    #### CLEAR PREFS ####

    # Clear GLOBAL prefs
    def clearGlobalPrefs(self):
        '''
        Clear all of the preferencs found in the global group/namespace
        '''
        # Clear the global widget prefs
        self.clearGroup(self.GROUP_GLOBAL_WIDGETS)

        # Call the parent method to clear the global prefs (non-widgets)
        super(UiFilePrefs, self).clearGlobalPrefs()

    # Clear GLOBAL prefs
    def clearFilePrefs(self, filepath):
        '''
        Clear all of the preferencs found in the given filepath's group/namespace
        '''
        # Clear the file widget prefs
        group = self.GROUP_FILE_WIDGETS + "/" + self.encodeGroupName(filepath)
        self.clearGroup(group)

        # Call the parent method to clear the global prefs (non-widgets)
        super(UiFilePrefs, self).clearFilePrefs(filepath)
