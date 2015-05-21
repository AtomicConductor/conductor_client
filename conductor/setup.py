
import os
import sys
import imp

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import conductor

import conductor.lib.common

try:
    CONFIG = conductor.lib.common.Config().config
except ValueError as e:
    raise

logger = conductor.lib.common.LOGGER
