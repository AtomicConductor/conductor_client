import logging
from conductor.lib import common, loggeria

#The version string is updated by the build system.
#Do not modify the following line.
#__version__="0.0.0"

# Read the config yaml file upon module import

logging.basicConfig()

try:
    CONFIG = common.Config().config
except ValueError:
    # wizard.run()
    CONFIG = common.Config().config

# IF there is log level specified in config (which by default there should be), then set it for conductor's logger
log_level = CONFIG.get("log_level")
if log_level:
    loggeria.set_conductor_log_level(log_level)
