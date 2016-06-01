import os
import sys
import imp
import logging
import tempfile
import warnings

from conductor.lib import common, loggeria, version_check

#The version string is updated by the build system.
#Do not modify the following line.
#__version__="0.0.0"

# Read the config yaml file upon module import
try:
    CONFIG = common.Config().config
except ValueError:
    #Launch the setup completion wizard here?
    raise

# IF there is log level specified in config (which by default there should be), then set it for conductor's logger
log_level = CONFIG.get("log_level")
if log_level:
    loggeria.set_conductor_log_level(log_level)
    
#Try to ensure that we have the latest version of Conductor
try:
    vc = version_check.VersionCheck()
    if not vc.is_latest:
        warnings.warn("Conductor is out of date.  Please go to {} for update information.".format(vc.update_url))
except:
    warnings.warn("Failed to check for Conductor updates.")
