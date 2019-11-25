# Unreleased


# v2.11.5 -  2019.11.25

* **Clarisse submitter:** 
  * Path manipulation code now runs on Windows only.

# v2.11.4 -  2019.11.19

* **Clarisse submitter:** 
  * Now handles windows path management offline by replacing paths in project files. In some situations links to resources in files with nested references could get erased while loading a project if all the references are not resolved. For this reason, its not sufficient to replace the paths in the session with the clarrisse sdk. Paths must be valid before the project loads. 
  * Fixed bug where render file would be cleaned up before the upload daemon had a chance to upload it.

# v2.11.3  -  2019.11.14

* **Clarisse submitter:**
  * Catch invalid glob path that caused Clarisse to crash.

# v2.11.1  -  2019.10.31

* **Uploader:**
    * Support Uploading to AWS Buckets.

# v2.10.1  -  2019.09.26

* **Clarisse submitter:**
  * Submitter title defaults to $PNAME.
  * Images attribute changed to images_and_layers.
  * Instance types menu entries are now ordered by machine spec.
  * Pre render script replaces backslashes as well as drive letters.
  * Better error on failure to make subdirectories.

# v2.10.0  -  2019.09.23

* **Submitter:** Instance type selection now supports Google Cloud's
    * n1-standard-1
    * n1-highcpu-2
    * n1-highcpu-4

* **Package auto-matching support**
  * **Golaem:** 7.0.1
  * **Maya:** 2018.6, 2019, 2019.1, 2019.2
  * **Maya to Arnold:** 3.1.2.1, 3.1.2.2, 3.2.0, 3.2.0.1, 3.2.0.2, 3.2.1, 3.2.2, 3.2.1.1, 3.3.0
  * **Nuke:** Nuke11.2v7, 11.3v5
  * **Renderman for Maya:** 21.8, 22.4, 22.5, 22.6
  * **V-Ray for Maya:** 4.04.03, 4.12.01, 4.12.02
  * **Yeti:** 3.1.15, 3.1.17, 3.5.1, 3.5.2

# v2.9.1  -  2019.08.30

* **Clarisse:**
  * **Layers:** Supports rendering of individual image layers without rendering the containing image.
  * **Missing files:** You can proceed with a render if some dependencies are missing. You are shown a list of missing files first. Offending files are removed from the upload list, which would previously cause a submission failure.
  * **clarisse.cfg:** Supports shipping of the clarisse.cfg file so that preferences such as "output AOV to separate files" are respected. It has been necessary to strip some UI-focused categories to avoid a crash on Windows.
  * **Localize contexts:** Choose between localizing contexts, or shipping the job with nested xrefs in tact. Due to a bug in the Clarisse undo mechanism after localizing contexts, the only way to restore the project previously was to reload a saved backup after submitting. Now we can handle shipping xrefs, there's no need to modify the scene before submission and therefore the whole operation is faster.
  * **Token substitution:** `<angle bracket tokens>` are now used to build the task command. The previous release used Clarisse `$VARIABLES` which could be confusing and less robust.
  * **CNODE arguments:** Some CLI args, like -license_server, -config_file, and -debug_level, have been moved into the wrapper in order to keep the task command clean. They are implemented as default values that make sense for submissions to the cloud, but can be overridden b,y including them in the task template.
  * **Path errors:** Dependency scanning now has improved handling and information display when badly formed paths are encountered.
  * Render package: Ship a regular project ASCII file to Conductor, in favour of the now deprecated render package binary.
  * **Clarisse version:**  Removed the over-complicated tree view widget for software package selection in favor of a dropdown menu.
  * **Validate output path:**  If several images or layers are being rendered to different locations, we determine the writable output as the common location among them. If this path turns out to be the root path, it is considered invalid.
