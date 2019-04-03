"""Script to be added to Clarisse's list of startup scripts.

It registers the conductor_job class in Clarisse.
"""

import ix
from ix.api import OfAttr, OfObjectFactory
from conductor.clarisse.scripted_class.conductor_job import ConductorJob


# import logging
# from conductor.lib import   loggeria 

# logger = logging.getLogger(__name__)


ix.api.ModuleScriptedClass.register_scripted_class(
    ix.application, "ConductorJob", ConductorJob())
