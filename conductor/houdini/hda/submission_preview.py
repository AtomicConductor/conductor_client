"""A window to preview a submission."""


from PySide2 import QtWidgets, QtGui, QtCore

from conductor.houdini.hda.submission_tree import SubmissionTree
from conductor.houdini.hda.submission_dry_run import SubmissionDryRun


class SubmissionPreview(QtWidgets.QTabWidget):

    def __init__(self, parent=None):
        QtWidgets.QTabWidget.__init__(self, parent)
        self.tree = SubmissionTree()
        self.dry_run = SubmissionDryRun()

        self.addTab(self.tree, "Tree")
        self.addTab(self.dry_run, "Dry run")

        self.setGeometry(300, 200, 1000, 600)
 
        self.setWindowTitle("Conductor submission preview")
