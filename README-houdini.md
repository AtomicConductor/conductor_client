
## Conductor Houdini client.



### Installation. 

Currently, the installers do not work for the Houdini environment, so you'll need to clone this trial branch and set up some variables.

```
git clone git@github.com:AtomicConductor/conductor_client.git`
cd conductor_client/
git checkout CT-181_houdini_alpha
```

You need to add to the `PYTHONPATH`, the `HOUDINI_PATH` and set `CONDUCTOR_CONFIG`. You can do this in `.bashrc` or alternatively, use the `houdini.env` file.

Example: .bashrc  on OSX

```
# CONDUCTOR_LOCATION is a convenience here in .bashrc, 
# It is also useful in the Houdini client if you want to 
# try custom script examples. Replace "/path/to" of course.
export CONDUCTOR_LOCATION=/path/to/conductor_client


# On OsX at least, PYTHONPATH needs the site-packages 
# below, in addition to CONDUCTOR_LOCATION

CONDUCTOR_PYTHONPATH="${CONDUCTOR_LOCATION}/installers/osx/python/lib/python2.7/site-packages:${CONDUCTOR_LOCATION}"
if [[ -n $PYTHONPATH ]]
    then export PYTHONPATH=${CONDUCTOR_PYTHONPATH}:${PYTHONPATH}
else 
    export PYTHONPATH=${CONDUCTOR_PYTHONPATH}
fi

# config file for OSX below. On linux it may be 
# $HOME/.conductor/config.yml or wherever.
export CONDUCTOR_CONFIG=${HOME}'/Library/Application Support/Conductor/config.yml'

# HOUDINI_PATH is where Houdini searches for digital assets. 
if [[ -n $HOUDINI_PATH ]]
then export HOUDINI_PATH="${HOUDINI_PATH};$CONDUCTOR_LOCATION/conductor/houdini"
else 
    export HOUDINI_PATH="$CONDUCTOR_LOCATION/conductor/houdini"
fi
```

You can also set `HOUDINI_PATH` in a [houdini.env file](http://www.sidefx.com/docs/houdini/basics/config_env.html)  
 

```
# conductor config start
HOUDINI_PATH = "$HOUDINI_PATH;$CONDUCTOR_LOCATION/conductor/houdini;&"
# conductor config end
```

In order to check if the plugin was installed properly launch Houdini and go to `/out` network. Verify that Conductor Job and Submitter tools appear under `Farm` section of the Tool Menu. If not, its likely your HOUDINI_PATH is incorrectly configured.


### Get started

#### To create a simple Mantra submission to Conductor:

* Open a scene containing some animation and a Mantra ROP that can render it.
* Choose `TAB Menu->Farm->Conductor job` in the `/out` network and drop a job node.

The first time you create a job, a request will be made to fetch information from Conductor, and if necessary you will be asked to authenticate. Once Authenticated you should be able to select a Conductor project in the Submission tab of the job.

* Connect the Mantra output to the job input. You should now see the **Preview** and **Submit** buttons are enabled in the submission tab.
* Press the **Preview** button to take a look at what will be submitted. Pay attention to the dry-run section.
* If all looks good in the preview, press the **Submit** button in the parameter interface.

If the submission was successful you'll see a dialog with a details section, where you'll find the Conductor URL for the job.


#### To set up multiple jobs in one submission:

* Create a second Mantra ROP with different values and create a new Conductor job node for it.
* Choose `TAB Menu->Farm->Conductor Submitter` in the `/out` network and drop a Submitter node.
* Connect the output of both job nodes to the submitter.
* Be sure to set the project in the submitter node.

The submitter node is a convenience for submitting many jobs with one button press. The parameters in the submitter ROP override those in the submitter tab of the job. If you press the **Preview** button you'll notice the submission now contains an array of 2 jobs. 

Use the submit button to submit both jobs in one go. The `$CT_TIMESTAMP` variable will have the same value for both jobs.

### Frame sequences and chunking


#### Custom frame specification
By default, the frame range to render is derived from the input node via an expression. If you chose to override the source frame range, you can specify an arbitrary set of frames with a **frame spec**. A frame spec is a string containing numbers or ranges delimited by commas. Ranges may have an optional step value, indicated by an `x`. Example: `1,7,10-20,30-60x3,1001,` Spaces and trailing commas are allowed, but not letters or other non-numeric characters.

A custom frame spec may be useful when a previous render failed on certain frames and you want to render only the failed frames on a machine with more power or memory.

#### Chunking
If a scene renders fast but is slow to load, it can make sense to render many frames in each task. A Conductor job can break the frame range into chunks so that tasks may be distributed to machines in the cloud. When you set the desired size of chunks, the resulting number of chunks will be displayed in the UI.

> By default, chunks will be arithmetic progressions. An arithmetic progression is a set of frames that can be expressed as start/end/step. Unless you are providing a custom render script that can handle an arbitrary frame spec, you should leave the `progressions` checkbox on. 


### Simulations

To cache a simulation, simply connect a Dynamics ROP. You'll notice the `frames` section disappears from the UI. A simulation is always run on one task and the frame range is always derived from the input ROP. You still have access to variables relating to the frame range in case you want to use them in the job title an so on.


#### Custom submission scripts

*in progress*

----

### Reference: Conductor job


#### Inputs
The ROP that will be rendered

#### General Parameters

**Update button** `update`
Small button top left in the UI. Force update of packages and projects from Conductor. Authenticates if necessary.


**Job title** `job_title`
This title will appear in the Conductor UI. 
You may use Houdini variables, including job-level Conductor variables to construct this string. To see a list of available Conductor variables and their values in the context of each job, use the Preview button and expand the Tokens section in the tree view.




**Use custom frame range** `use_custom`
Override the frame range defined in the input ROP.


**Start/end/inc** `fs`
Start, end, and step value for a regular frame range. These are always derived from the input ROP. 


**Custom range** `custom_range`
Specify a custom frameset to override the range from the input ROP. A custom range is valid when it is a comma-separated list of arithmetic progressions. These can be formatted as single numbers or ranges with a hyphen and optionally a step value signified by an x. Example, 1,7,10-20,30-60x3,1001, Spaces and trailing commas are allowed, Letters and other non-numeric characters are not. The order is not important.


**Chunk size** `chunk_size`
Set the number of frames in a chunk. A chunk is a set of frames that will be rendered in one task. you may want to use chunks greater than one if the number of instances is limited, or if the time to load the scene is large compared to the time to process frames. Use the AUTO button to adjust the chunk size such that frames are distributed as evenly as possible while retaining the current number of chunks. For example, if chunk size is 70 and there are 100 frames, 2 chunks will be generated with 70 and 30 frames. Hit the AUTO button to even them out and set chunk size to 50.


**Auto button** `auto_chunk_size`
Set the best distribution of frames per chunk based on the current number of chunks. For example, if chunk size is 70 and there are 100 frames, 2 chunks will be generated with 70 and 30 frames. It would be better to have 50 frames per chunk and this method returns that number. Auto chunk size is not applicable when chunk strategy is progressions.


**Progressions** `progressions`
When using a custom frame range, specify that chunks must be progressions. Progressions are frame ranges that can be expressed as a start, end, and step. If you use a task command that requires start/end/step parameters, such as `hrender`, then you'll need valid values for the variables $CT_CHUNKSTART, $CT_CHUNKEND, $CT_CHUNKSTEP. Setting progressions to on will ensure the sequence is split into chunks where this is true. If you don't override frame range, then the sequence itself is a progression and will always generate chunks that are progressions.


**Scout** `do_scout`
Choose to start just a subset of frames before running the complete job. 


**Scout frames** `scout_frames`
Specify frames you want to see rendered before deciding whether the render the whole job. Use a frame spec of the same format as the custom frames parameter. Scout frames that are not in the frame range will be ignored. For example, if the frame range is 1-10 and scout frames are 9-11, only 9 and 10 will be resolved as valid scout frames. Further, scout frames signify whether or not to start the task they were included in. For example, if chunk size is 10 and the first task contains frames 1-10, then specifying 5 as a scout frame will cause the task to be started running. Only tasks that have no scout frames will be initialized on hold.


**Machine type** `machine_type`
Choose a machine type on which to run this job.


**Preemptible** `preemptible`
Choose whether this machine can be preempted by another process and restarted. Preemptible machines are less expensive, especially for short jobs that are unlikely to be preempted.


**Retries** `retries`
Set how many times a preempted task will be retried automatically.


**Job metadata** `metadata`
Data as key/value pairs that may be attached to the job. This metadata may be useful later for filtering usage charts and so on. You may use Houdini variables, including job-level Conductor variables, to construct these strings. To see a list of available Conductor variables and their values in the context of each job, use the Preview button and expand the Tokens section in the Tree view.

#### Advanced Parameters

**Task command** `task_command`
Command that will be run at conductor on each instance. By default, this will be set to `hrender`, Houdini's command line render script. You may also provide your own. There are some examples provided by Conductor, see the Custom scripts section above. 

You can use Houdini variables, including job-level Conductor variables, to construct this command. You will likely want to pass the scene name and the source ROP path to the command. These are stored in variables $CT_SCENE and $CT_SOURCE. $CT_SCENE is guaranteed to be the scene that will be uploaded, whether it is the normal scene name or a timestamped version of the scene that is saved automatically. To see a list of available Conductor variables and their values in the context of each job, use the Preview button and expand the Tokens section in the Tree view. 


**Choose packages button** `choose_software`
Choose one or more licensed software packages that Conductor has installed. The chooser contains a tree of software dependencies. At the top level are host versions of Houdini, and if plugins are available they are parented to hosts. If you choose a plugin or any package other than a Houdini package, all its ancestors up to the Houdini will be added. It is not necessary that the Houdini version you choose is the same as the current session. The current version may not be available. What matters is that the command you run can execute in the context of the software you choose.


**Autodetect button** `detect_software`
Detect the current Houdini version and any plugins in use. If Conductor has the exact versions available, add them to the list of packages to use. If the exact versions are not available, use the choose button instead to select acceptable versions.


**Clear packages button** `clear_software`
Clear the list of software packages.


**Extra uploads** `extra_upload_paths`
Specify paths to extra resources you want to upload for this job. If you specify a script to run in the task command, you'll want to include it here, along with any other libraries or packages it depends on, so they are available when the task launches on Conductor's instances.


**Extra environment** `environment_kv_pairs`
If any scripts are being uploaded in the extra upload paths section, you may want to provide paths or other environment variables here so they can be found. You can use this section to set or append to any variables you like, for example, to run Houdini with verbose debug output.


**Output directory** `output_directory`
The directory that will be made available for download. By default, there is an expression to get the directory from the output image parameter on the source ROP. As the parameter name is different for each type of ROP, it can only find the path for node types it knows about. If you have an input ROP connected and you see "None" in the output directory, either edit the expression so it can find the correct path in your ROP or simply delete the expression and add a path manually.

#### Submission Parameters

**Preview button** `preview`
Preview the whole submission in two views.

* Tree view: shows the whole submission object, including available variables. 
* Dry run: shows the JSON array of jobs that will be submitted.


**Autosave with timestamp** `use_timestamped_scene`
Choose to write out a scene file automatically using the filename with a timestamp suffix. The timestamp used will also be available as a variable and can be useful to keep the scene associated with renders. It also improves workflow as you don't need to think about filenames every time you send a render job.


**Submit button** `submit`
Submit the job to Conductor.

**Project** `project`
Choose the Conductor project in which to run the job.


**Local upload** `local_upload`
    Currently, local upload is always on. In future, it will be possible to use a Conductor upload daemon to take care of file uploads on a machine other than the local workstation. 


**Force upload** `force_upload`
    When force upload is on, files will be uploaded regardless of whether they already exist at Conductor.


**Upload only** `upload_only `
    Do not run any tasks. Only upload files. 


**Email addresses** `email_addresses`
    Enter a comma-delimited list of email addresses that will be notified when the job completes or fails. Disabled if no email hooks are selected.


**On submit** `email_on_submit`
    Currently not used


**On start** `email_on_start `
    Currently not used


**On finish** `email_on_finish`
    Send an email on completion


**On failure** `email_on_failure`
    Currently not used
 


### Reference: Conductor submitter

*wip*










