
# v2.9.1  -  2019.08.30

#### Added

* **Clarisse > Layers:** Supports rendering of individual image layers without rendering the containing image.

* **Clarisse > Missing dependencies:**  Allows you to proceed with a render if some dependencies are missing. You are shown a list of missing files first. Offending files are removed from the upload list, which would previously cause a submission failure.

* **Clarisse > Upload clarisse.cfg:** Supports shipping of the clarisse.cfg file so that preferences such as "output AOV to separate files" are respected. It has been necessary to strip some UI-focused categories to avoid a crash on Windows.

* **Clarisse > Localize contexts:** Allows you to choose between localizing contexts, or shipping the job with nested xrefs in tact. Due to a bug in the Clarisse undo mechanism after localizing contexts, the only way to restore the project previously was to reload a saved backup after submitting. Now we can handle shipping xrefs, there's no need to modify the scene before submission and therefore the whole operation is faster.

* **Clarisse > Token substitution:** \<angle bracket tokens> are now used to build the task command. The previous release used Clarisse $VARIABLES which could be confusing and less robust.

* **Clarisse > CNODE arguments** Some CLI args, like -license_server, -config_file, and -debug_level, have been moved into the wrapper in order to keep the task command clean. They are implemented as default values that make sense for submissions to the cloud, but can be overridden by simply including them in the task template.

* **Clarisse > Path errors**  Dependency scanning now has improved handling and information display when badly formed paths are encountered.

* **Clarisse > Render package**  Save a regular project to ship to Conductor, in favour of the now deprecated render package binary.

* **Clarisse > Clarisse version**  Removed the over-complicated tree view widget for software package selection in favor of a dropdown menu.

* **Clarisse > Validate output path**  If several images or layers are being rendered to different locations, we determine the writable output as the common location among them. If this path turns out to be the root path, it is considered invalid and.


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
