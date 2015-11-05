#!/bin/bash -ex

# This script allows an optional user and/or group id to be specifed.
# The conductor executable will be run as this UID/GID.
# Both default to 10000 if not specified.

# set CONDUCTOR_UID to specified value or 10000 if unset
CONDUCTOR_UID=${CONDUCTOR_UID-10000}

# set CONDUCTOR_GID to specified value or 10000 if unset
CONDUCTOR_GID=${CONDUCTOR_GID-10000}

# create conductor group with GID = CONDUCTOR_GID
groupadd -g $CONDUCTOR_GID conductor

# create conductor user with UID CONDUCTOR_UID, and default group CONDUCTOR_GID
useradd -u $CONDUCTOR_UID -g $CONDUCTOR_GID -d /conductor conductor

# make all files in /conductor ownned by conductor:conductor
chown -R $CONDUCTOR_UID:$CONDUCTOR_GID /conductor/

# execute conductor
command="/conductor/bin/conductor $@"
exec su - conductor --preserve-environment -c "$command"
