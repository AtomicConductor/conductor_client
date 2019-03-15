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
    "CT_SOURCE",
    "CT_TYPE",
    "CT_SCOUT",
    "CT_CHUNKSIZE",
    "CT_CHUNKCOUNT",
    "CT_SCOUTCOUNT",
    "CT_TIMESTAMP",
    "CT_SUBMITTER",
    "CT_SCENE",
    "CT_PROJECT",
    "CT_CHUNKTYPE",
    "CT_CHUNK",
    "CT_CHUNKLENGTH",
    "CT_CHUNKSTART",
    "CT_CHUNKEND",
    "CT_CHUNKSTEP"
]


def declare():
    for varname in CONDUCTOR_VARS:
        put(varname, "")


def put(varname, value):
    all_vars = ix.application.get_factory().get_vars()
    v = all_vars.get(varname)
    if not v:
        v = all_vars.add(
            ix.api.OfVars.TYPE_CUSTOM,
            varname,
            ix.api.OfAttr.TYPE_STRING)
    v.set_string(value)


def get(varname):
    v = ix.application.get_factory().get_vars().get(varname)
    if v:
        return v.get_string()
