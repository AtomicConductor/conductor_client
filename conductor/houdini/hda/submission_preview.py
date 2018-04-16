import hou
from conductor.houdini.hda.submission_dry_run import SubmissionDryRun
from conductor.houdini.hda.submission_tree import SubmissionTree
from PySide2 import QtWidgets


class SubmissionPreview(QtWidgets.QTabWidget):
    """A Window to display views into the submission.

    There are 2 tabs. One to show the whole object tree
    including variables available to the user. The other to
    show the JSON objects that will be submitted.
    """

    def __init__(self, parent=None):
        QtWidgets.QTabWidget.__init__(self, parent)

        self.tree = SubmissionTree()
        self.dry_run = SubmissionDryRun()

        self.addTab(self.tree, "Tree")
        self.addTab(self.dry_run, "Dry run")

        self.setGeometry(300, 200, 1000, 600)

        self.setWindowTitle("Conductor submission preview")
        self.setStyleSheet(hou.qt.styleSheet())
 