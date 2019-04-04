"""Script to be added to Clarisse's list of startup scripts.

It registers the conductor_job class in Clarisse.
"""

import ix

from conductor.clarisse.scripted_class.conductor_job import ConductorJob

ix.api.ModuleScriptedClass.register_scripted_class(
    ix.application, "ConductorJob", ConductorJob())
