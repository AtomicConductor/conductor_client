import gzip
import json
import logging

from conductor.lib import api_client
logger = logging.getLogger(__name__)


def fetch_job_by_jid(jid):
    endpoint = "api/v1/jobs"
    params = {"filter": "jid_eq_%s" % jid}

    client = api_client.ApiClient()
    response, code = client.make_request(uri_path=endpoint, params=params)
    logger.debug("code: %s", code)
    jobs = json.loads(response).get("data")
    assert len(jobs) <= 1, "More than one Job %s found!" % jid
    if not jobs:
        raise Exception("Job %s not found" % jid)
    return jobs[0]


def fetch_job_by_id(job_id):
    endpoint = "api/v1/jobs/%s" % job_id
    client = api_client.ApiClient()
    response, code = client.make_request(uri_path=endpoint)
    logger.debug("code: %s", code)
    return json.loads(response).get("data")


def fetch_upload(upload_id):
    endpoint = "api/v1/uploads/%s" % upload_id
    client = api_client.ApiClient()
    response, code = client.make_request(uri_path=endpoint)
    logger.debug("code: %s", code)
    return json.loads(response).get("data")


def fetch_task_by_id(task_id):
    endpoint = "api/v1/tasks/%s" % task_id
    client = api_client.ApiClient()
    response, code = client.make_request(uri_path=endpoint)
    logger.debug("code: %s", code)
    return json.loads(response).get("data")


def fetch_task_by_jidtid(jid, tid):
    endpoint = "api/v1/tasks"
    params = {"filter": "jid_eq_%s,tid_eq_%s" % (jid, tid)}

    client = api_client.ApiClient()
    response, code = client.make_request(uri_path=endpoint, params=params)
    logger.debug("code: %s", code)
    tasks = json.loads(response).get("data")
    assert len(tasks) <= 1, "More than one Task %s-%s found!" % (jid, tid)
    if not tasks:
        raise Exception("Task %s-%s not found" % (jid, tid))
    return tasks[0]


def set_upload_status(upload_id, status):
    endpoint = "api/v1/uploads/%s" % upload_id
    client = api_client.ApiClient()
    response, code = client.make_request(uri_path=endpoint, verb="PUT", data=json.dumps({"status": status}))
    logger.debug("code: %s", code)
    return json.loads(response).get("data")


def write_json_file(jdict, filepath, compress=True):

    if compress:
        filepath += ".gz"
        with gzip.open(filepath, 'wb') as f:
            f.write(json.dumps(jdict, sort_keys=True, indent=4))
    else:
        with open(filepath, "w") as f:
            f.write(json.dumps(jdict, sort_keys=True, indent=4))

    logger.debug("Written to: %s", filepath)


def read_json_file(filepath):

    if filepath.endswith(".gz"):
        with gzip.open(filepath, 'rb') as f:
            return json.loads(f.read())
    else:
        with open(filepath, "r") as f:
            return json.loads(f.read())
