"""Declare variables that users can use to construct strings.

These variables are available to help construct the job title, task
command, metadata and so on. Most of the time, the attributes that use
them wont be changed and can even be hidden. However, when a user wants
to do something a little more advanced, for examplem create their own
cnode wrapper, they will find them useful. It should be noted that these
variables should only be relied on by ConductorJob nodes, and only
during the submission process, and not by other nodes in Clarisse.
"""
import ix

CONDUCTOR_VARS = [
    "CT_SEQLENGTH",
    "CT_SEQUENCE",
    "CT_SEQUENCEMIN",
    "CT_SEQUENCEMAX",
    "CT_CORES",
    "CT_FLAVOR",
    "CT_INSTANCE",
    "CT_PREEMPTIBLE",
    "CT_RETRIES",
    "CT_JOB",
    "CT_SOURCES",
    "CT_TYPE",
    "CT_SCOUT",
    "CT_CHUNKSIZE",
    "CT_CHUNKCOUNT",
    "CT_SCOUTCOUNT",
    "CT_TIMESTAMP",
    "CT_SUBMITTER",
    "CT_RENDER_PACKAGE",
    "CT_PROJECT",
    "CT_CHUNKTYPE",
    "CT_CHUNKS",
    "CT_CHUNKLENGTH",
    "CT_CHUNKSTART",
    "CT_CHUNKEND",
    "CT_CHUNKSTEP",
    "CT_DIRECTORIES",
    "CT_PDIR"
]


def declare():
    """Make sure they are all present and have a value."""
    for varname in CONDUCTOR_VARS:
        put(varname, "deferred")


def put(varname, value):
    """Take the pain out of setting an envvar in Clarisse."""
    all_vars = ix.application.get_factory().get_vars()
    var = all_vars.get(varname)
    if not var:
        var = all_vars.add(
            ix.api.OfVars.TYPE_CUSTOM,
            varname,
            ix.api.OfAttr.TYPE_STRING)
    var.set_string(value)


def get(varname):
    """Take the pain out of getting an envvar in Clarisse."""
    var = ix.application.get_factory().get_vars().get(varname)
    return var.get_string() if var else None
