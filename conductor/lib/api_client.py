import json
import logging
from pprint import pformat
import os
import re
import requests
import sys
import time
import types
import urlparse
import jwt

from conductor import CONFIG
from conductor.lib import common, auth, openapi

# A convenience tuple of network exceptions that can/should likely be retried by the retry decorator
CONNECTION_EXCEPTIONS = (requests.exceptions.HTTPError,
                         requests.exceptions.ConnectionError,
                         requests.exceptions.Timeout,
                         )
logger = logging.getLogger(__name__)

RESOURCE_JOBS = "jobs"
RESOURCE_METADATA = "metadata"
RESOURCE_PACKAGES = "ee/packages"
RESOURCE_PROJECTS = "projects"
RESOURCE_SIDECARS = "ee/sidecars"
RESOURCE_TASKS = "tasks"
RESOURCE_UPLOADS = "uploads"


# TODO:
# appspot_dot_com_cert = os.path.join(common.base_dir(),'auth','appspot_dot_com_cert2')
# load appspot.com cert into requests lib
# verify = appspot_dot_com_cert

# global/cached token
bearer_token = None


def get_bearer_token(reuse=True):
    global bearer_token
    if not bearer_token or not reuse:
        bearer_token = read_conductor_credentials(use_api_key=False)
    return bearer_token


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


'''
Authorization can occur through two methods:
    - user credentials
    - api key 



'''



def get_api_key():
    '''
    There are two places 
    '''
    creds_file = os.path.join(config_path, "api_key_credentials")

    config_path = os.path.join(os.path.expanduser("~"), ".config", "conductor")

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
    response, response_code = api.make_request(uri_path=uri, verb="GET", raise_on_error=False, use_api_key=True)
    logger.debug("response: %s", response)
    logger.debug("response: %s", response_code)
    if response_code not in [200]:
        msg = "Failed to get available projects from Conductor"
        msg += "\nError %s ...\n%s" % (response_code, response)


class HttpRequest(object):

    @classmethod
    def request(cls, http_method, url, headers=None, params=None, json_data=None, raise_error=True):
        logger.debug("http_method: %r", http_method)
        logger.debug("url: %r", url)
        logger.debug("headers: %r", headers)
        logger.debug("params: %r", params)
        logger.debug("json_data: %r", json_data)

        response = requests.request(http_method, url, headers=headers, params=params, json=json_data)

        if raise_error:
            response.raise_for_status()

        return response

    @classmethod
    def get(cls, url, headers=None, params=None, raise_error=True):
        return cls.request("GET", url, headers=headers, params=params, raise_error=raise_error)

    @classmethod
    def post(cls, url, headers=None, params=None, json_data=None, raise_error=True):
        return cls.request("POST", url, headers=headers, params=params, json_data=json_data, raise_error=raise_error)

    @classmethod
    def put(cls, url, headers=None, params=None, json_data=None, raise_error=True):
        return cls.request("PUT", url, headers=headers, params=params, json_data=json_data, raise_error=raise_error)

    @classmethod
    def patch(cls):
        raise NotImplementedError()

    @classmethod
    def delete(cls):
        raise NotImplementedError()

    @classmethod
    def head(cls):
        raise NotImplementedError()


class AppRequest(HttpRequest):
    '''
    For making requests to Conductor
    '''

    @classmethod
    def app_request(cls, http_method, endpoint, headers=None, params=None, json_data=None, use_api_key=False, raise_error=True):
        headers = headers if headers != None else {}
        auth_header = cls.get_authorization_header(use_api_key)
        headers.update(auth_header)
        url = cls.construct_url(endpoint)
        return cls.request(http_method, url, headers=headers, params=params, json_data=json_data, raise_error=raise_error)

    @classmethod
    def get_authorization_header(cls, use_api_key=False):
        bearer_token = read_conductor_credentials(use_api_key)
        if not bearer_token:
            raise Exception("Error: Could not get conductor credentials!")

        return {'Authorization': "Bearer %s" % bearer_token}

    @classmethod
    def get_base_url(cls):
        return CONFIG['url']

    @classmethod
    def construct_url(cls, endpoint):
        '''
        <base_url>/<endpoint>/
        e.g. "https://conductor.conductorio.com/jobs/
        '''
        base_url = cls.get_base_url()
        print "base_url", base_url
        print "endpoint", endpoint

        return urlparse.urljoin(base_url, endpoint)


class ResourceRequest(AppRequest):
    '''
    For making resource requests to Conductor
    '''

    API_VERSION = 1

    @classmethod
    def request_resource(cls, http_method, resource_name, resource_id=None, headers=None, params=None, json_data=None, raise_error=True):
        resource_endpoint = cls.construct_resource_endpoint(resource_name, resource_id)
        return cls.app_request(http_method, resource_endpoint, headers=headers, params=params, json_data=json_data, raise_error=raise_error)

    @classmethod
    def get(cls, resource_name, resource_id=None, headers=None, params=None, raise_error=True):
        return cls.request_resource("GET", resource_name, resource_id=resource_id, headers=headers, params=params, raise_error=raise_error)

    @classmethod
    def post(cls, resource_name, resource_attributes=None, headers=None, params=None, raise_error=True):
        return cls.request_resource("POST", resource_name, headers=headers, params=params, json_data=resource_attributes, raise_error=raise_error)

    @classmethod
    def put(cls, resource_name, resource_id, resource_attributes=None, headers=None, params=None, raise_error=True):
        return cls.request_resource("PUT", resource_name, resource_id=resource_id, headers=headers, params=params, json_data=resource_attributes, raise_error=raise_error)

    @classmethod
    def delete(cls, resource_name, resource_id, resource_attributes=None, headers=None, params=None, raise_error=True):
        return cls.request_resource("DELETE", resource_name, resource_id=resource_id, headers=headers, params=params, json_data=resource_attributes, raise_error=raise_error)

    @classmethod
    def construct_resource_endpoint(cls, resource_name, resource_id=None):
        '''
        <base_url>/api/v<api_version>/<resource_name>/[<resource_id>]>
        e.g. "https://conductor.conductiorio.com/v1/jobs/9830498304870348"

        Note that a trailing slash should only be used when targeting a "resource 
        group", .e.g  GET "/jobs/".  However, when targeting a resource via a 
        specific ID, there should NEVER be trailing slash.
        '''

        # If no resource_id argument was provided, default it an empty string
        resource_id = "" if resource_id == None else resource_id

        return "api/v{}/{}/{}".format(cls.API_VERSION, resource_name, resource_id)


def get_resource(resource_name, resource_id=None, headers=None, params=None, raise_error=True):

    response = ResourceRequest.get(resource_name, resource_id=resource_id, headers=headers, params=params, raise_error=raise_error)
    if response.status_code not in [200]:
        msg = "Failed to GET available %s from Conductor" % resource_name
        msg += "\nError %s %s\n%s" % (response.status_code, response.reason, response.content)
        raise Exception(msg)

    json_data = response.json()
    resource_data = json_data.get("data")
    if resource_data == None:
        raise Exception('Json response does not have expected key: "data"\nJson data: \n%s' % json_data)

    return resource_data


def post_resource(resource_name, resource_attributes, headers=None, params=None, raise_error=True):

    response = ResourceRequest.post(resource_name, resource_attributes=resource_attributes, headers=headers, params=params, raise_error=raise_error)
    if response.status_code not in [201]:
        msg = "Failed to POST %s to Conductor" % resource_name
        msg += "\nError %s %s\n%s" % (response.status_code, response.reason, response.content)
        raise Exception(msg)

    json_data = response.json()
    resource_data = json_data.get("data")
    if resource_data == None:
        raise Exception('Json response does not have expected key: "data"\nJson data: \n%s' % json_data)

    return resource_data


def put_resource(resource_name, resource_id, resource_attributes, headers=None, params=None, raise_error=True):

    response = ResourceRequest.put(resource_name, resource_id, resource_attributes=resource_attributes, headers=headers, params=params, raise_error=raise_error)
    if response.status_code not in [200]:
        msg = "Failed to PUT %s to Conductor" % resource_name
        msg += "\nError %s %s\n%s" % (response.status_code, response.reason, response.content)
        raise Exception(msg)

    json_data = response.json()
    resource_data = json_data.get("data")
    if resource_data == None:
        raise Exception('Json response does not have expected key: "data"\nJson data: \n%s' % json_data)

    return resource_data


def delete_resource(resource_name, resource_id, headers=None, params=None, raise_error=True):

    response = ResourceRequest.delete(resource_name, resource_id, headers=headers, params=params, raise_error=raise_error)
    if response.status_code not in [200]:
        msg = "Failed to PUT %s to Conductor" % resource_name
        msg += "\nError %s %s\n%s" % (response.status_code, response.reason, response.content)
        raise Exception(msg)

    json_data = response.json()
    resource_data = json_data.get("data")
    if resource_data == None:
        raise Exception('Json response does not have expected key: "data"\nJson data: \n%s' % json_data)

    return resource_data


def get_projects(statuses=("active",)):
    '''
    Query Conductor for all client Projects that are in the given state(s)
    '''
    logger.debug("statuses: %s", statuses)

    projects = []

    for project in get_resource(resource_name=RESOURCE_PROJECTS):
        if not statuses or project.get("status") in statuses:
            projects.append(project)

    return projects


def get_software_packages():
    '''
    Query Conductor for all client Projects that are in the given state(s)
    '''
    from conductor.lib import software_packages_cached
    return software_packages_cached.PACKAGES

    return get_resource(resource_name=RESOURCE_PACKAGES)


def get_sidecars():
    '''
    Return the sidecar entity for the given sidecar_id.  If no sidecar_id is
    given, return the latest sidecar
    '''
    return get_resource(resource_name=RESOURCE_SIDECARS)

# #---------
# # JOBS
# #---------
# def get_job(resource_id, params=None):
#     return get_resource(RESOURCE_JOBS, resource_id=resource_id, params=params)
#
# def post_job(**attributes):
#     return post_resource(RESOURCE_JOBS, resource_attributes=attributes)
#
# def put_job(resource_id, **resource_attributes):
#     return put_resource(RESOURCE_JOBS, resource_id, resource_attributes=resource_attributes)
#
# #---------
# # TASKS
# #---------
# def get_task(resource_id, params=None):
#     return get_resource(RESOURCE_TASKS, resource_id=resource_id, params=params)
#
# def post_task(**attributes):
#     return post_resource(RESOURCE_TASKS, resource_attributes=attributes)
#
# def put_task(resource_id, **attributes):
#     return put_resource(RESOURCE_TASKS, resource_id, resource_attributes=attributes)
#
# #---------
# # METADATA
# #---------
# def get_metadata(resource_id, params=None):
#     return get_resource(RESOURCE_METADATA, resource_id=resource_id, params=params)
#


def post_metadata(**attributes):
    return post_resource(RESOURCE_METADATA, resource_attributes=attributes)
#
# def put_metadata(resource_id, **attributes):
#     return put_resource(RESOURCE_METADATA, resource_id, resource_attributes=attributes)
#
# #---------
# # UPLOADS
# def get_upload(resource_id, params=None):
#     return get_resource(RESOURCE_UPLOADS, resource_id=resource_id, params=params)
# #---------
# def post_upload(**attributes):
#     '''
#     attributes:
#         owner: str
#         upload_files*: dict
#         status*: str.
#         location: str
#         project*: str. id of the project entity
#         metadata:int. id of the metadata entity
#         total_size* = int. total byes of all files in the upload
#     '''
#     return post_resource(RESOURCE_UPLOADS, resource_attributes=attributes)
#
# def put_upload(resource_id, **attributes):
#     return put_resource(RESOURCE_UPLOADS, resource_id, resource_attributes=attributes)


class Resource(object):

    RESOURCE = None

    @classmethod
    @common.dec_retry(retry_exceptions=CONNECTION_EXCEPTIONS, tries=5)
    def get(cls, id_=None, params=None):
        return get_resource(cls.RESOURCE, resource_id=id_, params=params)

    @classmethod
    @common.dec_retry(retry_exceptions=CONNECTION_EXCEPTIONS, tries=5)
    def post(cls, attributes):
        return post_resource(cls.RESOURCE, resource_attributes=attributes)

    @classmethod
    @common.dec_retry(retry_exceptions=CONNECTION_EXCEPTIONS, tries=5)
    def put(cls, id_, attributes):
        return post_resource(cls.RESOURCE, resource_attributes=attributes)


class JobResource(Resource):
    RESOURCE = "jobs"


class MetadataResource(Resource):
    RESOURCE = "metadata"
    METADATA_TYPES = types.StringTypes

    @classmethod
    def put(cls, id_, attributes):
        attributes = cls.cast_metadata(attributes, strict=True)
        super(MetadataResource, cls).put(id_, attributes)

    @classmethod
    def cast_metadata(cls, metadata, strict=False):
        '''
        Ensure that the data types in the given metadata are of the proper type
        (str or unicode). If strict is False, automatically cast (and warn)
        any values which do not conform.  If strict is True, do not cast values,
        simply raise an exception.  
        '''

        # Create a new metadata dictionary to return
        casted_metadata = {}

        # reusable error/warning message
        error_msg = 'Metadata %%s %%s is not of a supported type. Got %%s. Expected %s' % " or ".join([type_.__name__ for type_ in cls.METADATA_TYPES])

        for key, value in metadata.iteritems():

            key_type = type(key)
            if key_type not in cls.METADATA_TYPES:
                msg = error_msg % ("key", key, key_type)
                if strict:
                    raise Exception(msg)
                logger.warning(msg + ".  Auto casting value...")
                key = cls.cast_metadata_value(key)

            value_type = type(value)
            if value_type not in cls.METADATA_TYPES:
                msg = error_msg % ("value", value, value_type)
                if strict:
                    raise Exception(msg)
                logger.warning(msg + ".  Auto casting value...")
                value = cls.cast_metadata_value(value)

            # This should never happen, but need to make sure that the casting
            # process doesn't cause the original keys to collide with one another
            if key in casted_metadata:
                raise Exception("Metadata key collision due to casting: %s", key)
            casted_metadata[key] = value

        return casted_metadata

    @classmethod
    def cast_metadata_value(cls, value):
        '''
        Attempt to cast the given value to a unicode string
        '''

        # All the types that are supported for casting to metadata type
        cast_types = (bool, int, long, float, str, unicode)

        value_type = type(value)

        cast_error = "Cannot cast metadata value %s (%s) to unicode" % (value, value_type)

        # If the value's type is not one that can be casted, then raise an exception
        if value_type not in cast_types:
            raise Exception(cast_error)

        # Otherwise, attempt to cast the value to unicode
        try:
            return unicode(value)
        except:
            cast_error = "Casting failure. " + cast_error
            logger.error(cast_error)
            raise


class UploadResource(Resource):
    RESOURCE = "uploads"


class TaskBatchResource(Resource):
    RESOURCE = "task_batch"


class Resource(object):
    '''
    Represents an openapi "operation" (by way of Bravado object).

    An operation is a request to specific endpoint
    '''
    OP_ID_GET = None
    OP_ID_POST = None
    OP_ID_PUT = None
    OP_ID_PATCH = None
    OP_ID_DELETE = None

    MODEL_NAME = None
    RESOURCE_NAME = None  # e.g. openapi "tag"

    def __init__(self, openapi_client=None, user_token=None, api_key=None):
        '''
        '''
        self._openapi_client = openapi_client or openapi.get_client()
        self._model = self._openapi_client.get_model(self.MODEL_NAME) if self.MODEL_NAME else None
        self._resource = getattr(self._openapi_client, self.RESOURCE_NAME) if self.RESOURCE_NAME else None
        self._get_func = self._get_get_func()
        self._post_func = self._get_post_func()
        self._user_token = user_token if user_token is not None else self._get_user_token()
        self._api_key = api_key if api_key is not None else self._get_api_key()

    def get(self, args, headers=None, use_api_key=False):
        headers = self._get_headers(headers, use_api_key=use_api_key)
        return self._get(args, headers=headers, use_api_key=use_api_key)

    def _get(self, args):
        headers
        return self._get_func(args)

    def _get_get_func(self):
        return getattr(self._resource, self.OP_ID_GET) if self.OP_ID_GET else None

    def post(self, args):
        return self._post(args)

    def _post(self, attrs):
        print "%s resource_attrs: %s" % (self.RESOURCE_NAME, pformat(attrs))
        model = self._model(**attrs)
        headers = {"authorization": "Bearer %s" % self._openapi_client._bearer_token}
        return self._post_func(body=model, _request_options={"headers": headers}).result()

    def _get_post_func(self):
        return getattr(self._resource, self.OP_ID_POST) if self.OP_ID_POST else None

    def _get_headers(self, headers, use_api_key=False):
        if use_api_key:
            if not self._api_key:
                raise Exception("No Api key available.  TODO ...This must be specified either in config or environment variable")
            token = self._api_key
        else:
            
        headers = headers if headers != None else {}
        auth_header = cls.get_authorization_header(use_api_key)
        headers.update(auth_header)
        url = cls.construct_url(endpoint)
        return cls.request(http_method, url, headers=headers, params=params, json_data=json_data, raise_error=raise_error)

    @classmethod
    def get_authorization_header(cls, use_api_key=False):
        bearer_token = read_conductor_credentials(use_api_key)
        if not bearer_token:
            raise Exception("Error: Could not get conductor credentials!")

        return {'Authorization': "Bearer %s" % bearer_token}

get_bearer_token


class Metadata(Resource):
    OP_ID_GET = "getMetadata"
    OP_ID_POST = "postMetadata"
    OP_ID_PUT = "putMetadata"


def snake_case(string):
    '''
    https://stackoverflow.com/questions/1175208/elegant-python-function-to-convert-camelcase-to-snake-case
    '''
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', string)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def camel_case(string):
    '''
    https://stackoverflow.com/questions/19053707/converting-snake-case-to-lower-camel-case-lowercamelcase
    '''
    components = string.split('_')
    # We capitalize the first letter of each component except the first one
    # with the 'title' method and join them together.
    return components[0] + "".join(x.title() for x in components[1:])


if __name__ == "__main__":
    metadata = Metadata()
    print metadata.post({"items": {"cool": "beans"}})
