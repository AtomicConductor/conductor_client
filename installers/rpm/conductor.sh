#!/bin/bash
#/etc/profile.d/conductor.sh
#conductor environment setup
export PYTHONPATH=$PYTHONPATH:/opt/conductor/python/lib/python2.7/site-packages:/opt/conductor
export MAYA_SHELF_PATH=$MAYA_SHELF_PATH:/opt/conductor/maya_shelf
export XBMLANGPATH=$XBMLANGPATH:/opt/conductor/conductor/resources/%B
export HOUDINI_PATH=$HOUDINI_PATH:/opt/conductor/houdini
export NUKE_PATH=$NUKE_PATH:/opt/conductor/nuke_menu
export CONDUCTOR_CONFIG=$HOME/.conductor/config.yml
export CONDUCTOR_LOCATION=/opt/conductor


export PATH=$PATH:/opt/conductor/bin