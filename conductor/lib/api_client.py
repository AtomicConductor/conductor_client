import json
import logging
import os
import requests
import time
import urlparse
import jwt

from conductor import CONFIG
from conductor.lib import common, auth

logger = logging.getLogger(__name__)

# A convenience tuple of network exceptions that can/should likely be retried by the retry decorator
CONNECTION_EXCEPTIONS = (requests.exceptions.HTTPError,
                         requests.exceptions.ConnectionError,
                         requests.exceptions.Timeout)

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

        logger.debug("verb: %s", verb)
        logger.debug("conductor_url: %s", conductor_url)
        logger.debug("headers: %s", headers)
        logger.debug("params: %s", params)
        logger.debug("data: %s", data)

        # If we get 300s/400s debug out the response. TODO(lws): REMOVE THIS
        if response.status_code and 300 <= response.status_code < 500:
            logger.debug("*****  ERROR!!  *****")
            logger.debug("Reason: %s" % response.reason)
            logger.debug("Text: %s" % response.text)

        # trigger an exception to be raised for 4XX or 5XX http responses
        if raise_on_error:
            response.raise_for_status()

#         logger.debug('response.status_code: %s', response.status_code)
#         logger.debug('response.text is: %s', response.text)
        return response

    def make_request(self, uri_path="/", headers=None, params=None, data=None,
                     verb=None, conductor_url=None, raise_on_error=True, tries=5,
                     use_api_key=False):
        '''
        verb: PUT, POST, GET, DELETE, HEAD, PATCH
        '''


        # TODO: set Content Content-Type to json if data arg
        if not headers:
            headers = {'Content-Type':'application/json',
                       'Accept':'application/json'}
#         logger.debug('headers are: %s', headers)
#         logger.debug('data is: %s' % data)
#         logger.debug("params is %s" % params)
#         logger.debug("uri path is %s" % uri_path)

        # headers['Authorization'] = "Token %s" % CONFIG['conductor_token']
        bearer_token = read_conductor_credentials(use_api_key)
        if not bearer_token:
            raise Exception("Error: Could not get conductor credentials!")

        headers['Authorization'] = "Bearer %s" % bearer_token

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

        # Create a retry wrapper function
        retry_wrapper = common.DecRetry(retry_exceptions=CONNECTION_EXCEPTIONS,
                                        tries=tries)

        # wrap the request function with the retry wrapper
        wrapped_func = retry_wrapper(self._make_request)

        # call the wrapped request function
        response = wrapped_func(verb, conductor_url, headers, params, data,
                                      raise_on_error=raise_on_error)

        return response.text, response.status_code


def read_conductor_credentials(use_api_key=False):
    '''
    Read the conductor credentials file, if it exists. This will contain a bearer token from either the user
    or the API key (if that's desired). If the credentials file doesn't exist, try and fetch a new one in the
    API key scenario or prompt the user to log in.
    Args:
        use_api_key: Whether or not to use the API key

    Returns: A Bearer token in the event of a success or None if things couldn't get figured out

    '''

    logger.debug("Reading conductor credentials...")
    if use_api_key and not CONFIG.get('api_key') or not CONFIG.get('api_key', {}).get('client_id') \
            or not CONFIG.get('api_key', {}).get('private_key'):
        use_api_key = False

    logger.debug("use_api_key = %s" % use_api_key)
    creds_file = get_creds_path(use_api_key)

    logger.debug("Creds file is %s" % creds_file)

    if not os.path.exists(creds_file):
        if use_api_key:
            if not CONFIG.get('api_key'):
                logger.debug("Attempted to use API key, but no api key in in config!")
                return None

            #  Exchange the API key for a bearer token
            logger.debug("Attempting to get API key bearer token")
            get_api_key_bearer_token(creds_file)

        else:
            auth.run(creds_file)

    if not os.path.exists(creds_file):
        return None

    logger.debug("Reading credentials file...")
    with open(creds_file) as fp:
        file_contents = json.loads(fp.read())

    expiration = file_contents.get('expiration')
    if not expiration or expiration < int(time.time()):
        logger.debug("Credentials expired!")
        if use_api_key:
            logger.debug("Refreshing API key bearer token!")
            get_api_key_bearer_token(creds_file)
        else:
            logger.debug("Sending to auth page...")
            auth.run(creds_file)

    return file_contents['access_token']


def get_api_key_bearer_token(creds_file=None):
    response = requests.get("%s/api/oauth_jwt" % CONFIG['url'],
                            params={"grant_type": "client_credentials",
                                    "scope": "owner admin user",
                                    "client_id": CONFIG['api_key']['client_id'],
                                    "client_secret": CONFIG['api_key']['private_key']})
    if response.status_code == 200:
        response_dict = json.loads(response.text)
        credentials_dict = {
            "access_token": response_dict['access_token'],
            "token_type": "Bearer",
            "expiration": int(time.time()) + int(response_dict['expires_in']),
            "scope": "user admin owner"
        }

        if not creds_file:
            return credentials_dict

        with open(creds_file, "w") as fp:
            fp.write(json.dumps(credentials_dict))
    return


def account_id_from_jwt(token):
    """
    Fetch the accounts id from a jwt token value.
    """
    payload = jwt.decode(token, verify=False)
    return payload.get("account")


def account_name_from_jwt(token):
    """
    Fetch the accounts name from a jwt token value.
    """
    account_id = account_id_from_jwt(token)
    if account_id:
        url = "%s/api/v1/accounts/%s" % (CONFIG['api_url'], account_id)
        response = requests.get(url, headers={"authorization": "Bearer %s" % token})
        if response.status_code == 200:
            response_dict = json.loads(response.text)
            return response_dict["data"]["name"]
    return None


def get_creds_path(api_key=False):
    # config = common.Config()
    # config_path = os.path.dirname(config.get_config_file_path())
    config_path = os.path.join(os.path.expanduser("~"), ".config", "conductor")
    if api_key:
        creds_file = os.path.join(config_path, "api_key_credentials")
    else:
        creds_file = os.path.join(config_path, "credentials")
    return creds_file


def request_projects(statuses=("active",)):
    '''
    Query Conductor for all client Projects that are in the given state(s)
    '''
    api = ApiClient()

    logger.debug("statuses: %s", statuses)

    uri = 'api/v1/projects/'

    response, response_code = api.make_request(uri_path=uri, verb="GET", raise_on_error=False, use_api_key=True)
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

    response, response_code = api.make_request(uri_path=uri, verb="GET", raise_on_error=False,
                                               use_api_key=True)
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
    response, response_code = api.make_request(uri_path=uri, verb="GET", raise_on_error=False,
                                               use_api_key=True)
    logger.debug("response: %s", response)
    logger.debug("response: %s", response_code)
    if response_code not in [200]:
        msg = "Failed to get sidecar from %s" % uri
        msg += "\nError %s ...\n%s" % (response_code, response)
        raise Exception(msg)

    return json.loads(response)
