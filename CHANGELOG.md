# v1.0.2  -  2016.07.22

#### Added

* **Projects**: Jobs are now submitted and organized by a given _project_ (supplanting the _resource_ argument).

* **Software Packages selection**: Users can now select which software versions they would like their job to be executed with.

* **Scout Frames**: A cost-saving mechanism that facilitates the partial rendering of a job before fully commiting to rendering its entirety.

* **Metadata**: Jobs can be submitted with arbitrary metadata values (key/value pairs).

* **Downloader optimization for small files**: Downloader now downloads many small files efficently (batch querying).

* **Downloader verbosity/output**: The downloader now prints out more revant information (active threads, queued downloads, etc)

#### Removed

* **Resource**: The _resource_ argument has been removed from job submission (supplanted by _project_).
