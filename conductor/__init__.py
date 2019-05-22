from conductor.lib import common, loggeria

# The version string is updated by the build system. (No it isn't)
# Do not modify the following line.
# __version__="0.0.0"

# Read the config yaml file upon module import
try:
    CONFIG = common.Config().config
except ValueError:
    CONFIG = common.Config().config


# Must setup logging before setting the level, otherwise we get a
# complaint about no handlers for logger conductor.
loggeria.setup_conductor_logging()
log_level = CONFIG.get("log_level")
if log_level:
    loggeria.set_conductor_log_level(log_level)
