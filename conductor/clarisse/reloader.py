"""
For development mode, we can reload modules with a button push.



The button is available when the env var CONDUCTOR_MODE == "dev".
It reloads files imported by ConductorJob. Not ConductorJob itself.
"""
from conductor.clarisse import utils, clarisse_config
from conductor.clarisse.scripted_class import (
    attr_docs,
    debug_ui,
    dependencies,
    environment_ui,
    extra_uploads_ui,
    frames_ui,
    instances_ui,
    job,
    missing_files_ui,
    notifications_ui,
    packages_ui,
    preview_ui,
    projects_ui,
    refresh,
    submission,
    submit_actions,
    task,
)
from conductor.native.lib import gpath, gpath_list, sequence

reload(utils)
reload(clarisse_config)
reload(refresh)
reload(dependencies)
reload(debug_ui)
reload(gpath_list)
reload(gpath)
reload(sequence)
reload(environment_ui)
reload(extra_uploads_ui)
reload(missing_files_ui)
reload(frames_ui)
reload(instances_ui)
reload(job)
reload(task)
reload(notifications_ui)
reload(packages_ui)
reload(projects_ui)
reload(submission)
reload(submit_actions)
reload(preview_ui)
reload(attr_docs)
