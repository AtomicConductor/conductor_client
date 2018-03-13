# from hou import qt


from PySide2 import QtWidgets, QtGui, QtCore


class SubmissionTree(QtWidgets.QWidget):

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        hbox = QtWidgets.QHBoxLayout()
        self.setGeometry(300, 200, 1000, 600)
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

        self._appendRow(self._model, "Submission node:", submission["submission"])
        self._appendRow(self._model, "Hip file:", submission["filename"])
        self._appendRow(self._model, "Unsaved changes:", str(submission["unsaved"]))



        token_item = self._appendRow(self._model, "Tokens:")
        for t in sorted(submission["tokens"]):
            self._appendRow(token_item, t, submission["tokens"][t])
        # index = self._model.indexFromItem(token_item)
        self._view.expand(self._model.indexFromItem(token_item))
 

        jobs_item = self._appendRow(self._model, "Jobs:")
        self._view.expand(self._model.indexFromItem(jobs_item))
        for i, j in enumerate(submission["jobs"]):
            job_item = self._appendRow( jobs_item, j["node_name"])
            self._appendRow(job_item, "Title:", j["title"])
            self._appendRow(job_item, "Scene file:", j["scene_file"])

            self._appendRow(job_item, "Source node:", j["source"])
            self._appendRow(job_item, "Source type:", j["type"])
            self._appendRow(job_item, "Project id:", j["project"])


            if not i:
                self._view.expand(self._model.indexFromItem(job_item))
 

            if j["notifications"]:
                email_item = self._appendRow(job_item, "Email notifications:")
                addresses_item = self._appendRow(email_item, "Addresses:")
                for i, address in enumerate(sorted(j["notifications"]["email"]["addresses"])):
                    self._appendRow(addresses_item,  "[%d]" % i, address)
                hooks_item = self._appendRow(email_item, "Hooks:")
                for hook in j["notifications"]["email"]["hooks"]:
                    self._appendRow(hooks_item,  hook[0], str(hook[1]))
  
            deps_item =  self._appendRow(job_item, "Dependencies:")
            for i, d in enumerate(j["dependencies"]):
                self._appendRow(deps_item, "[%d]" % i, d)

            metatdata_item = self._appendRow(job_item, "Job Metadata:")
            for k, v in j["metadata"].iteritems():
                self._appendRow(metatdata_item, k, v)

            packages_item = self._appendRow(job_item, "Package IDs:")
            for i, p in enumerate(j["package_ids"]):
                self._appendRow(packages_item, "[%d]" % i, p)


            environment_item = self._appendRow(job_item, "Environment:")
            for  envkey in  sorted(j["environment"]):
                self._appendRow(environment_item,  envkey , j["environment"][envkey])


            job_token_item = self._appendRow(job_item, "Tokens:")
            for t in sorted(j["tokens"]):
                self._appendRow(job_token_item, t, j["tokens"][t])
            

            task_item = self._appendRow(job_item, "Tasks:")
            self._view.expand(self._model.indexFromItem(task_item))
 
            for ii, t in enumerate(j["tasks"]):
                task_header = self._appendRow(task_item, "[%d] %s" % (ii,  str(t["clump"])) )
                task_command_item = self._appendRow(task_header, "Command:",  t["command"] )
                task_frames_item = self._appendRow(task_header, "Frames:",  str(tuple(t["clump"])) )            
                task_token_item = self._appendRow(task_header, "Tokens:")
                for tok in sorted(t["tokens"]):
                    self._appendRow(task_token_item, tok, t["tokens"][tok])

                if not ii:
                    self._view.expand(self._model.indexFromItem(task_header))

 
