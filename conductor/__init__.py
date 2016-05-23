import os
import sys
import imp
import logging
import tempfile
import webbrowser

from conductor.lib import common, loggeria

#__version__="0.0.0"

# Read the config yaml file upon module import
try:
    CONFIG = common.Config().config
except ValueError:
    #Launch the setup completetion wizard here?
    raise

# IF there is log level specified in config (which by default there should be), then set it for conductor's logger
log_level = CONFIG.get("log_level")
if log_level:
    loggeria.set_conductor_log_level(log_level)
