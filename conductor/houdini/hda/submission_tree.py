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

        self._appendRow(self._model, "Submission node:", submission.node_name)
        self._appendRow(self._model, "Hip file:", submission.filename)
        self._appendRow(self._model, "Scene file:", str(submission.scene))
        self._appendRow(self._model, "Use timestamped:", str(submission.use_timestamped_scene))
        self._appendRow(self._model, "Force upload:", str(submission.force_upload))
        self._appendRow(self._model, "Local upload:", str(submission.local_upload))

        self._appendRow(
            self._model, "Unsaved changes:", str(
                submission.unsaved))

        token_item = self._appendRow(self._model, "Tokens:")
        for t in sorted(submission.tokens):
            self._appendRow(token_item, t, submission.tokens[t])
        self._view.expand(self._model.indexFromItem(token_item))

        jobs_item = self._appendRow(self._model, "Jobs:")
        self._view.expand(self._model.indexFromItem(jobs_item))

        for i, job in enumerate(submission.jobs):
            job_item = self._appendRow(jobs_item, job.node_name)
            self._appendRow(job_item, "Title:", job.title)

            self._appendRow(job_item, "Source path:", job.source_path)
            self._appendRow(job_item, "Source type:", job.source_type)
            self._appendRow(job_item, "Project id:", job.project_id)

            if i is 0:
                self._view.expand(self._model.indexFromItem(job_item))

            if job.has_notifications():
                email_item = self._appendRow(job_item, "Email notifications:")
                addresses_item = self._appendRow(email_item, "Addresses:")
                for i, address in enumerate(sorted(job.email_addresses)):
                    self._appendRow(addresses_item, "[%d]" % i, address)
                hooks_item = self._appendRow(email_item, "Hooks:")
                for hook in job.email_hooks:
                    self._appendRow(hooks_item, hook[0], str(hook[1]))

            deps_item = self._appendRow(job_item, "Dependencies:")
            if job.dependencies:
                for i, d in enumerate(job.dependencies):
                    self._appendRow(deps_item, "[%d]" % i, d)
            else: 
                self._appendRow(deps_item, "No dependencies")

            metatdata_item = self._appendRow(job_item, "Job Metadata:")
            if job.metadata:
                for k, v in job.metadata.iteritems():
                    self._appendRow(metatdata_item, k, v)
            else: 
                self._appendRow(metatdata_item, "No metadata")

            packages_item = self._appendRow(job_item, "Package IDs:")
            for i, p in enumerate(job.package_ids):
                self._appendRow(packages_item, "[%d]" % i, p)

            environment_item = self._appendRow(job_item, "Environment:")
            for envkey in sorted(job.environment):
                value = job.environment[envkey]
                parts = value.split(":")
                var_item = self._appendRow(
                    environment_item,
                    envkey,
                    job.environment[envkey])
                if len(parts) > 1:
                    for pindex, part in enumerate(parts):
                        self._appendRow(var_item[0], "[%d]" % pindex, part)



            job_token_item = self._appendRow(job_item, "Tokens:")
            for t in sorted(job.tokens):
                self._appendRow(job_token_item, t, job.tokens[t])

            task_item = self._appendRow(job_item, "Tasks:")
            self._view.expand(self._model.indexFromItem(task_item))

            for j, task in enumerate(job.tasks):
                task_header = self._appendRow(
                    task_item, "[%d] %s" % (j, str(task.clump)))
                self._appendRow(task_header, "Command:", task.command)
                self._appendRow(task_header, "Frames:", str(tuple(task.clump)))
                task_token_item = self._appendRow(task_header, "Tokens:")
                for tok in sorted(task.tokens):
                    self._appendRow(task_token_item, tok, task.tokens[tok])

                if j is 0:
                    self._view.expand(self._model.indexFromItem(task_header))
