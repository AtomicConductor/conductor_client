from PySide import QtGui
from conductor.submitter_clarisse import ClarisseConductorSubmitter
import pyqt_clarisse
app = QtGui.QApplication(["Clarisse"])
ui = ClarisseConductorSubmitter()
ui.show()
pyqt_clarisse.exec_(app)