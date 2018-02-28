# from hou import qt


from PySide2 import QtWidgets, QtGui, QtCore


class SubmissionTree(QtWidgets.QWidget):

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        hbox = QtWidgets.QHBoxLayout()
        self.setGeometry(500, 500, 500, 500)
        self.setWindowTitle('Conductor dry run')

        self._view = QtWidgets.QTreeView()
        self._view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        self._model = QtGui.QStandardItemModel()
        self._model.setHorizontalHeaderLabels(['key', 'value'])
        self._view.setModel(self._model)
        self._view.setColumnWidth(0, 200)
        self._view.setUniformRowHeights(True)

        hbox.addWidget(self._view)

        self.setLayout(hbox)

    # @staticmethod
    def appendRow(self, parent, key, value=None):
        row = QtGui.QStandardItem(key)
        if value:
            row = [row, QtGui.QStandardItem(value)]
        parent.appendRow(row)
        return row
        # self._view.setFirstColumnSpanned(0, self._view.rootIndex(), False)

    def populate(self, submission):
        # model = QtGui.QStandardItemModel()
        # model.setHorizontalHeaderLabels(['key', 'value'])
        # self._view.setModel(model)
        # self._view.setUniformRowHeights(True)

        self.appendRow(self._model, "Submitter node:", submission["submitter"])
        self.appendRow(self._model, "Hip file:", submission["filename"])
        self.appendRow(self._model, "Source node:", submission["source"])
        self.appendRow(self._model, "Source type:", submission["type"])
        self.appendRow(self._model, "Project id:", submission["project"])

        token_item = self.appendRow(self._model, "Tokens:")
        for t in submission["tokens"]:
            self.appendRow(token_item, t, submission["tokens"][t])

        job_item = self.appendRow(self._model, "Jobs:")
        for i, j in enumerate(submission["jobs"]):
            job_title_item = self.appendRow(
                job_item, "[%d] %s" %
                (i, j["title"]))
            self.appendRow(job_title_item, "Scene file:", j["scene_file"])
            job_token_item = self.appendRow(job_title_item, "Tokens:")
            for t in j["tokens"]:
                self.appendRow(job_token_item, t, j["tokens"][t])

        # for i in range(5):
        #     parent1 = QtGui.QStandardItem(
        #         'Family {}. Some long status text for sp'.format(i))
        #     for j in range(3):
        #         child1 = QtGui.QStandardItem('Child {}'.format(i * 3 + j))
        #         child2 = QtGui.QStandardItem(
        #             'row: {}, col: {}'.format(i, j + 1))
        #         child3 = QtGui.QStandardItem(
        #             'row: {}, col: {}'.format(i, j + 2))
        #         parent1.appendRow([child1, child2, child3])
        #     model.appendRow(parent1)
        #     # span container columns

            # self._view.setFirstColumnSpanned(i, self._view.rootIndex(), True)

    # def __init__(self, submission):
    #     self._obj = submission
    #     self._build_tree()

    # def _build_tree(self):
