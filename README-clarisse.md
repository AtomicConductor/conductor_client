
## Conductor Clarisse client.



### Installation. 

Currently, the installers do not set up the Clarisse environment, so you'll need to clone this alpha branch and set up some variables.

```
git clone git@github.com:AtomicConductor/conductor_client.git`
cd conductor_client/
git checkout CT-911-clarisse-alpha
```

You need to add to the `PYTHONPATH`, the `PATH` and set `CONDUCTOR_CONFIG`. You can do this in `.bashrc` or alternatively, use the `clarisse.env` file.

Example: .bashrc  on OSX

```


export CONDUCTOR_LOCATION=/path/to/conductor_client


# On OsX at least, PYTHONPATH needs the site-packages 
# below, in addition to CONDUCTOR_LOCATION

PYTHONPATH=${CONDUCTOR_LOCATION}/installers/osx/python/lib/python2.7/site-packages:${CONDUCTOR_LOCATION}:${PYTHONPATH}
 
# config file for OSX below. On linux it may be 
# $HOME/.conductor/config.yml or wherever.
export CONDUCTOR_CONFIG=${HOME}'/Library/Application Support/Conductor/config.yml'

export CLARISSE_VERSION="4.0-SP1"
export CLARISSE_LOCATION="/Applications/Clarisse-iFX-${CLARISSE_VERSION}/clarisse.app/Contents/MacOS"
export PYTHONPATH="${CLARISSE_LOCATION}/python":${PYTHONPATH}
 
PATH="${CLARISSE_LOCATION}:$PATH"
export PATH
```

Finally, you need to add the location of the Clarisse ScriptedClass: ConductorJob to your startup scripts. 
In Clarisse, open preferences, it should be on the General tab already. In the Startup Script field add the following path: 

```
/path/to/conductor_client/conductor/clarisse/startup.py
```
 
### Get started

#### To create a submission to Conductor:

* Open a scene containing some image nodes to be rendered.

* Right click `New->ConductorJob`.
* Add images to be rendered to the images section in the attribute editor.

*docs in progress*


### Frame sequences and chunking


#### Custom frame specification
By default, the frame range to render is derived from the image nodes. If you chose to override the image frame ranges, you can specify an arbitrary set of frames with a **frame spec**. A frame spec is a string containing numbers or ranges delimited by commas. Ranges may have an optional step value, indicated by an `x`. Example: `1,7,10-20,30-60x3,1001,` Spaces and trailing commas are allowed, but not letters or other non-numeric characters.

A custom frame spec may be useful when a previous render failed on certain frames and you want to render only the failed frames on a machine with more power or memory.

#### Chunking
If a scene renders fast but is slow to load, it can make sense to render many frames in each task. A ConductorJob can break the frame range into chunks so that tasks may be distributed to machines in the cloud. When you set the desired size of chunks, the resulting number of chunks will be displayed in the UI.

#### Custom submission scripts

*in progress*









