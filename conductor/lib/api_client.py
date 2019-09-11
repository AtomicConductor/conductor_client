import json
import logging
import multiprocessing
import os
import requests
import time
import urlparse
import jwt

from conductor import CONFIG
from conductor.lib import common, auth

logger = logging.getLogger(__name__)

# Reusable authentication token  used across all processes/threads
BEARER_TOKEN = multiprocessing.Array('c', 2000)

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
            headers = {'Content-Type': 'application/json',
                       'Accept': 'application/json'}
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
    logger.debug("Auth url is %s" % CONFIG.get('auth_url'))
    if not os.path.exists(creds_file):
        if use_api_key:
            if not CONFIG.get('api_key'):
                logger.debug("Attempted to use API key, but no api key in in config!")
                return None

            #  Exchange the API key for a bearer token
            logger.debug("Attempting to get API key bearer token")
            get_api_key_bearer_token(creds_file)

        else:
            auth.run(creds_file, CONFIG.get('auth_url'))

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
            auth.run(creds_file, CONFIG.get('auth_url'))

        #  Re-read the creds file, since it has been re-upped
        with open(creds_file) as fp:
            file_contents = json.loads(fp.read())

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

        if not os.path.exists(os.path.dirname(creds_file)):
            os.makedirs(os.path.dirname(creds_file))

        with open(creds_file, "w") as fp:
            fp.write(json.dumps(credentials_dict))
    return


def get_bearer_token(refresh=False):
    '''
    Return the bearer token from a cached(global) variable.  If there is no
    cached value, then fetch a new bearer token and return it (and cache it).

    Note that that BEARER_TOKEN is not a simple string.  It's a process/thread-safe
    object.
    '''
    global BEARER_TOKEN

    if refresh or not BEARER_TOKEN.value:
        BEARER_TOKEN.value = read_conductor_credentials(True)

    return BEARER_TOKEN


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


def retrieve_instance_types(as_dict=False):
    '''
    Get the list of available instances types.
    '''
    bearer = get_bearer_token()
    account_id = account_id_from_jwt(bearer.value)

    api = ApiClient()
    response, response_code = api.make_request('api/v1/instance-types',
                                               use_api_key=True,
                                               raise_on_error=False)
    if response_code not in (200, ):
        msg = "Failed to get instance types"
        msg += "\nError %s ...\n%s" % (response_code, response)
        raise Exception(msg)

    # The 'data' k/v contains the list of instance types in the following format:
    # [
    #    {cores: 16, description: "16 core, 64GB Mem", name: "m5.4xlarge", memory: 64.0}
    #    {cores: 48, description: "48 core, 192GB Mem", name: "m5.12xlarge", memory: 192.0}
    # ]
    instance_types = json.loads(response).get('data', [])
    logger.debug('Found available instance types: %s', instance_types)

    if as_dict:
        return dict([(instance["description"], instance) for instance in instance_types])
    return instance_types


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


def request_software_packages():
    '''
    Query Conductor for all software packages for the currently available sidecar.
    '''
    api = ApiClient()

    uri = 'api/v1/ee/packages'
    response, response_code = api.make_request(uri_path=uri, verb="GET", raise_on_error=False,
                                               use_api_key=True)
#     logger.debug("response: %s", response)
#     logger.debug("response: %s", response_code)
    if response_code not in [200]:
        msg = "Failed to get software packages for latest sidecar"
        msg += "\nError %s ...\n%s" % (response_code, response)
        raise Exception(msg)
    return json.loads(response).get("data", [])
