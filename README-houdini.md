
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
# and is useful in the Houdini client if you want to try 
# custom script examples. Replace /path/to of 
# course.
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

### Get started















