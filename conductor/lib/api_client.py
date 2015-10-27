import json
import requests
import urlparse

import conductor.setup
from conductor.lib import common

logger = conductor.setup.logger
CONFIG = conductor.setup.CONFIG


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

        # trigger an exception to be raised for 4XX or 5XX http responses
        if raise_on_error:
            response.raise_for_status()

        return response

    def make_request(self, uri_path="/", headers=None, params=None, data=None,
                     verb=None, conductor_url=None, raise_on_error=True):
        '''
        verb: PUT, POST, GET, DELETE, HEAD, PATCH
        '''


        # TODO: set Content Content-Type to json if data arg
        if not headers:
            headers = {'Content-Type':'application/json'}
        # logger.debug('headers are: %s', headers)

        headers['Authorization'] = "Token %s" % CONFIG['conductor_token']

        # Construct URL
        if not conductor_url:
            conductor_url = urlparse.urljoin(CONFIG['url'], uri_path)
        # logger.debug('conductor_url: %s', conductor_url)

        if not verb:
            if data:
                verb = 'POST'
            else:
                verb = 'GET'

        assert verb in self.http_verbs, "Invalid http verb: %s" % verb
        response = common.retry(lambda: self._make_request(verb, conductor_url,
                                                            headers, params, data,
                                                            raise_on_error=raise_on_error))


        # logger.debug('response.status_code: %s', response.status_code)
        # logger.debug('response.text is: %s', response.text)
        return response.text, response.status_code


def request_docker_image(software_info):
    '''
    Query the app for an image that satisfies the given software_info requirements
   
    args:
        software_info: dict. e.g. {"software":"maya",
                                   "maya": "2015",
                                   "vray":"3.0",
                                   "golaem": "3.0.4"}

        return: str. the name of the docker image
    '''
    api = ApiClient()

    logger.debug("software_info: %s", software_info)

    uri = 'api/get_docker_image'

    response, response_code = api.make_request(uri_path=uri, params=software_info, raise_on_error=False)
    logger.debug("response: %s", response)
    if response_code not in [200]:
        msg = "Failed to retrieve docker image with the given paramaters:\n%s" % software_info
        msg += "\nError %s ...\n%s" % (response_code, response)
        raise Exception(msg)
    data = json.loads(response)
    return data["docker_image"]