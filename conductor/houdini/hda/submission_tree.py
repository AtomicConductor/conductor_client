from PySide2 import QtGui, QtWidgets


def appendRow(parent, key, value=None):
    row = QtGui.QStandardItem(key)
    if value:
        row = [row, QtGui.QStandardItem(value)]
    parent.appendRow(row)
    return row


class SubmissionTree(QtWidgets.QWidget):
    """A Window to display the submission object.

    Shows a tree view with expandable sections to view the
    whole state of the submission. The user can use this
    view to:
    1. Check or debug issues with the submission structure.
    2. check find out what tokens are available and
    what their values look like.
    """

    def __init__(self, parent=None):
        """Set up the UI for a tree view."""
        QtWidgets.QWidget.__init__(self, parent)
        hbox = QtWidgets.QHBoxLayout()

        self._view = QtWidgets.QTreeView()
        self._view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        self._model = QtGui.QStandardItemModel()
        self._model.setHorizontalHeaderLabels(['key', 'value'])
        self._view.setModel(self._model)
        self._view.setColumnWidth(0, 200)
        self._view.setUniformRowHeights(True)

        hbox.addWidget(self._view)

        self.setLayout(hbox)

    def populate(self, submission):
        """Put nicely formatted submission information in the tree widget."""
        appendRow(self._model, "Submission node:", submission.node_name)
        appendRow(self._model, "Hip file:", submission.filename)
        appendRow(
            self._model, "Submission scene:", str(
                submission.scene))
        appendRow(self._model, "Project id:", submission.project_id)

        appendRow(
            self._model, "Use timestamped:", str(
                submission.use_timestamped_scene))
        appendRow(
            self._model, "Force upload:", str(
                submission.force_upload))
        appendRow(
            self._model, "Local upload:", str(
                submission.local_upload))
        appendRow(
            self._model, "Upload only:", str(
                submission.upload_only))
        appendRow(
            self._model, "Unsaved changes:", str(
                submission.unsaved))

        if submission.has_notifications():
            email_item = appendRow(self._model, "Email notifications:")
            addresses_item = appendRow(email_item, "Addresses:")
            for i, address in enumerate(sorted(submission.email_addresses)):
                appendRow(addresses_item, "[%d]" % i, address)
            hooks_item = appendRow(email_item, "Hooks:")
            for hook in submission.email_hooks:
                appendRow(hooks_item, hook[0], str(hook[1]))
        else:
            appendRow(self._model, "Email notifications:", "False")

        token_item = appendRow(self._model, "Tokens:")
        for t in sorted(submission.tokens):
            appendRow(token_item, t, submission.tokens[t])
        self._view.expand(self._model.indexFromItem(token_item))

        jobs_item = appendRow(self._model, "Jobs:")
        self._view.expand(self._model.indexFromItem(jobs_item))

        for i, job in enumerate(submission.jobs):
            job_item = appendRow(jobs_item, job.node_name)
            appendRow(job_item, "Title:", job.title)

            appendRow(job_item, "Source path:", job.source_path)
            appendRow(job_item, "Source type:", job.source_type)

            appendRow(
                job_item,
                "Output directory:",
                job.output_directory)
            if i is 0:
                self._view.expand(self._model.indexFromItem(job_item))

            deps_item = appendRow(job_item, "Dependencies:")
            if job.dependencies:
                for i, d in enumerate(job.dependencies):
                    appendRow(deps_item, "[%d]" % i, d)
            else:
                appendRow(deps_item, "No dependencies")

            metatdata_item = appendRow(job_item, "Job Metadata:")
            if job.metadata:
                for k, v in job.metadata.iteritems():
                    appendRow(metatdata_item, k, v)
            else:
                appendRow(metatdata_item, "No metadata")

            packages_item = appendRow(job_item, "Package IDs:")
            for i, p in enumerate(job.package_ids):
                appendRow(packages_item, "[%d]" % i, p)

            environment_item = appendRow(job_item, "Environment:")
            job_env = dict(job.environment)
            for envkey in sorted(job_env):
                value = job_env[envkey]
                parts = value.split(":")
                var_item = appendRow(
                    environment_item,
                    envkey, value)
                if len(parts) > 1:
                    for pindex, part in enumerate(parts):
                        appendRow(var_item[0], "[%d]" % pindex, part)

            job_token_item = appendRow(job_item, "Tokens:")
            for t in sorted(job.tokens):
                appendRow(job_token_item, t, job.tokens[t])

            task_item = appendRow(job_item, "Tasks:")
            self._view.expand(self._model.indexFromItem(task_item))

            for j, task in enumerate(job.tasks):
                task_header = appendRow(
                    task_item, "%s" % str(task.chunk))
                appendRow(task_header, "Command:", task.command)
                appendRow(task_header, "Frames:", str(task.chunk))
                task_token_item = appendRow(task_header, "Tokens:")
                for tok in sorted(task.tokens):
                    appendRow(task_token_item, tok, task.tokens[tok])

                if j is 0:
                    self._view.expand(self._model.indexFromItem(task_header))
