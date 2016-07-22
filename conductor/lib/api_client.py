import json
import logging
from pprint import pformat
import requests
import urlparse

from conductor import CONFIG
from conductor.lib import common

logger = logging.getLogger(__name__)

# TODO:
# appspot_dot_com_cert = os.path.join(common.base_dir(),'auth','appspot_dot_com_cert2')
# load appspot.com cert into requests lib
# verify = appspot_dot_com_cert

class ApiClient():

    http_verbs = ["PUT", "POST", "GET", "DELETE", "HEAD", "PATCH"]

    def __init__(self):
        logger.debug('')


    def _make_request(self, verb, conductor_url, headers, params, data, raise_on_error=True):
        response = requests.request(verb, conductor_url,
                                    headers=headers,
                                    params=params,
                                    data=data)

#         logger.debug("verb: %s", verb)
#         logger.debug("conductor_url: %s", conductor_url)
#         logger.debug("headers: %s", headers)
#         logger.debug("params: %s", params)
#         logger.debug("data: %s", data)

        # trigger an exception to be raised for 4XX or 5XX http responses
        if raise_on_error:
            response.raise_for_status()

#         logger.debug('response.status_code: %s', response.status_code)
#         logger.debug('response.text is: %s', response.text)
        return response

    def make_request(self, uri_path="/", headers=None, params=None, data=None,
                     verb=None, conductor_url=None, raise_on_error=True):
        '''
        verb: PUT, POST, GET, DELETE, HEAD, PATCH
        '''


        # TODO: set Content Content-Type to json if data arg
        if not headers:
            headers = {'Content-Type':'application/json'}
#         logger.debug('headers are: %s', headers)
#         logger.debug('data is: %s' % data)
#         logger.debug("params is %s" % params)
#         logger.debug("uri path is %s" % uri_path)

        headers['Authorization'] = "Token %s" % CONFIG['conductor_token']

        # Construct URL
        if not conductor_url:
            conductor_url = urlparse.urljoin(CONFIG['url'], uri_path)
#         logger.debug('conductor_url: %s', conductor_url)

        if not verb:
            if data:
                verb = 'POST'
            else:
                verb = 'GET'

        assert verb in self.http_verbs, "Invalid http verb: %s" % verb
        response = common.retry(lambda: self._make_request(verb, conductor_url,
                                                            headers, params, data,
                                                            raise_on_error=raise_on_error))



        return response.text, response.status_code


def request_projects(statuses=("active",)):
    '''
    Query Conductor for all client Projects that are in the given state(s)
    '''
    api = ApiClient()

    logger.debug("statuses: %s", statuses)

    uri = 'api/v1/projects/'

    response, response_code = api.make_request(uri_path=uri, verb="GET", raise_on_error=False)
    logger.debug("response: %s", response)
    logger.debug("response: %s", response_code)
    if response_code not in [200]:
        msg = "Failed to get available projects from Conductor"
        msg += "\nError %s ...\n%s" % (response_code, response)
        raise Exception(msg)
    projects = []

    # Filter for only projects of the proper status
    for project in json.loads(response).get("data") or []:
        if not statuses or project.get("status") in statuses:
            projects.append(project["name"])
    return projects


def request_software_packages(sidecar_id=None):
    '''
    Query Conductor for all software packages for the given sidecar_id.  If no
    sidecar_id is given then get the latest packages (uses latest sidecar_id)
    '''
    api = ApiClient()

    logger.debug("sidecar_id: %s", sidecar_id)

    if sidecar_id:
        uri = 'api/v1/ee/packages/%s' % sidecar_id
    else:
        uri = 'api/v1/ee/packages'

    logger.debug("uri: %s", uri)

    response, response_code = api.make_request(uri_path=uri, verb="GET", raise_on_error=False)
#     logger.debug("response: %s", response)
#     logger.debug("response: %s", response_code)
    if response_code not in [200]:
        msg = "Failed to get software packages for sidecar: %s" % sidecar_id
        msg += "\nError %s ...\n%s" % (response_code, response)
        raise Exception(msg)
    return json.loads(response).get("data", [])


def request_sidecar(sidecar_id=None):
    '''
    Return the sidecar entity for the given sidecar_id.  If no sidecar_id is
    given, return the latest sidecar
    '''
    logger.debug("sidecar_id: %s", sidecar_id)

    api = ApiClient()
    uri = 'api/v1/ee/sidecars'
    if sidecar_id:
        uri += "/%s" % sidecar_id

    logger.debug("uri: %s", uri)
    response, response_code = api.make_request(uri_path=uri, verb="GET", raise_on_error=False)
    logger.debug("response: %s", response)
    logger.debug("response: %s", response_code)
    if response_code not in [200]:
        msg = "Failed to get sidecar from %s" % uri
        msg += "\nError %s ...\n%s" % (response_code, response)
        raise Exception(msg)

    return json.loads(response)


