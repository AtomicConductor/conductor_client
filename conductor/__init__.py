try:
    import conductor.lib.common

except ImportError as e:
    print "Failed to initialize Conductor"
    raise e

try:
    CONFIG = conductor.lib.common.Config().config
except ValueError as e:
    raise

logger = conductor.lib.common.LOGGER
