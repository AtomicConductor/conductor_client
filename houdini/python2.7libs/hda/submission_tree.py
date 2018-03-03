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

    def _appendRow(self, parent, key, value=None):
        row = QtGui.QStandardItem(key)
        if value:
            row = [row, QtGui.QStandardItem(value)]
        parent.appendRow(row)
        return row

    def populate(self, submission):

        self._appendRow(self._model, "Submitter node:", submission["submitter"])
        self._appendRow(self._model, "Hip file:", submission["filename"])
        self._appendRow(self._model, "Source node:", submission["source"])
        self._appendRow(self._model, "Source type:", submission["type"])
        self._appendRow(self._model, "Project id:", submission["project"])

        token_item = self._appendRow(self._model, "Tokens:")
        for t in sorted(submission["tokens"]):
            self._appendRow(token_item, t, submission["tokens"][t])

        jobs_item = self._appendRow(self._model, "Jobs:")
        for i, j in enumerate(submission["jobs"]):
            job_item = self._appendRow( jobs_item, j["take_name"])
            self._appendRow(job_item, "Title:", j["title"])
            self._appendRow(job_item, "Scene file:", j["scene_file"])

            deps_item =  self._appendRow(job_item, "Dependencies:")
            for i, d in enumerate(j["dependencies"]):
                self._appendRow(deps_item, "[%d]" % i, d)

            metatdata_item = self._appendRow(job_item, "Job Metadata:")
            for k, v in j["metadata"].iteritems():
                self._appendRow(metatdata_item, k, v)

            packages_item = self._appendRow(job_item, "Package IDs:")
            for i, p in enumerate(j["package_ids"]):
                self._appendRow(packages_item, "[%d]" % i, p)

            job_token_item = self._appendRow(job_item, "Tokens:")
            for t in sorted(j["tokens"]):
                self._appendRow(job_token_item, t, j["tokens"][t])


            task_item = self._appendRow(job_item, "Tasks:")
            for i, t in enumerate(j["tasks"]):
                task_header = self._appendRow(task_item, "[%d] %s" % (i,  str(t["clump"])) )
                self._appendRow(task_header, "Command:",  t["command"] )
                self._appendRow(task_header, "Frames:",  str(tuple(t["clump"])) )            
                task_token_item = self._appendRow(task_header, "Tokens:")
                for tok in sorted(t["tokens"]):
                    self._appendRow(task_token_item, tok, t["tokens"][tok])
