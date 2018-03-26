from PySide2 import QtWidgets, QtGui, QtCore


class SubmissionDryRun(QtWidgets.QWidget):
    """A Window to display jobs as JSON before sending.

    Shows JSON that represents the list of job submissions
    that will be sent to Conductor.
    """

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        hbox = QtWidgets.QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        self._text_area = QtWidgets.QTextEdit()
        self._text_area.setReadOnly(True)
        self._text_area.setWordWrapMode(QtGui.QTextOption.NoWrap)
        hbox.addWidget(self._text_area)
        self.setLayout(hbox)

    def populate(self, json):
        self._text_area.setText(json)
