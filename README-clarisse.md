
# Conductor Clarisse client.

The Conductor submitter for Clarisse is an item in your that allows you to ship render submissions to the Conductor cloud.


## Get started
### Installation.

See the documentation for Installing Conductor Client Tools.

### Register the submitter
The simplest way to register the submitter is to add it to your startup script.

Open Clarisse preferences and enter the following path in the *Startup script* section:

`$CONDUCTOR_LOCATION/conductor/clarisse/startup.py`

or on Windows:

`$CONDUCTOR_LOCATION\conductor\clarisse\startup.py`

This will kick in the next time you start Clarisse.

If you just want to try it out quickly, then import the startup file:

`from conductor.clarisse import startup`

Now look in the `Create` menu in Clarisse and you should see the `ConductorJob` option. 

If not, make sure `CONDUCTOR_LOCATION` is set and 


# To create a submission to Conductor:

* Open a scene containing some image nodes to be rendered.

* Right click `New -> ConductorJob`.
* Add some images to the images section in the attribute editor.
* Click the Setup button.
* .
* Add images to the images section in the attribute editor.

*docs in progress*


# Frame sequences and chunking


# Custom frame specification
By default, the frame range to render is derived from the image nodes. If you chose to override the image frame ranges, you can specify an.

A custom frame spec may be useful when a previous render failed on certain frames and you want to render only the failed frames on a machine with more power or memory.

# Chunking
If a scene renders fast but is slow to load, it can make sense to render many frames in each task. A ConductorJob can break the frame range into chunks so that tasks may be distributed to machines in the cloud. When you set the desired size of chunks, the resulting number of chunks will be displayed in the UI.
