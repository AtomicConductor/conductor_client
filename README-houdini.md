
## Conductor Houdini client.



### Installation. 

The installers do not currently set up the Houdini environment, so please clone this trial branch and set up some variables.

```
git clone git@github.com:AtomicConductor/conductor_client.git`
cd conductor_client/
git checkout CT-181_magic_trial
```

You need to add to the `PYTHONPATH`, the `HOUDINI_PATH` and set `CONDUCTOR_CONFIG`. You can do this in `.bashrc`. You can alternatively use the `houdini.env` file.

Example .bashrc  on OSX

```
# CONDUCTOR_LOCATION is a convenience here in .bashrc, 
# It is also useful in the Houdini client if you want to 
# try custom script examples. Replace "/path/to" of course.
export CONDUCTOR_LOCATION=/path/to/conductor_client


# On osx at least, PYTHONPATH needs the site-packages 
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

You can also set `HOUDINI_PATH` in a [houdini.env file](http://www.sidefx.com/docs/houdini/basics/config_env)  

```
# conductor config start
HOUDINI_PATH = "$HOUDINI_PATH;$CONDUCTOR_LOCATION/conductor/houdini;&"
# conductor config end
```

In order to check if the plugin was installed properly launch Houdini and go to `/out` network. Verify that Conductor Job and Submitter tools appears under `Farm` section of the Tool Menu. If not, its likeley your HOUDINI_PATH is incorrectly configured.


### Get started

#### To create a simple Mantra render submission to Conductor:

* Open a scene containing some animation and a Mantra ROP that can render it.
* Choose `TAB Menu->Farm->Conductor job` menu in the `/out` network and drop a Job node.

The first time you create a Job, a request will be made to fetch information from Conductor, and if necessary you will be asked to authenticate. Once Authenticated you should be able to select a Conductor project in the Submission tab of the Job ROP.

* Connect your Mantra Rop to the Job input. You should now see the **Preview** and **Submit** buttons are enabled.
* Press the **Preview** button to take a look at what will be submitted.
* If all looks good in the preview, press the submit button.

If the submission was successful you'll see a dialog with a details section, where you'll find the Conductor URL for the Job.














