import urlparse

import requests
from requests.auth import HTTPBasicAuth

import conductor, conductor.setup

from conductor.setup import *
from conductor.lib import common

class ApiClient():
    def __init__(self):
        logger.debug('')

    def get_token(self):
        userpass = "%s:unused" % CONFIG['conductor_token']
        return userpass

    def make_request(self, uri_path="/", headers=None, params=None, data=None, verb=None):
        '''
        verb: PUT, POST, GET, DELETE, HEAD
        '''

        # TODO: set Content Type to json if data arg
        if not headers:
            headers = {'Content-Type':'application/json'}
        logger.debug('headers are: %s', headers)


        # Construct URL
        conductor_url = urlparse.urljoin(CONFIG['url'], uri_path)
        logger.debug('conductor_url: %s', conductor_url)

        if not verb:
            if data:
                verb = 'POST'
            else:
                verb = 'GET'

        auth = CONFIG['conductor_token']

        response = common.retry(
            lambda:
            getattr(requests, verb.lower())(
                conductor_url,
                auth=HTTPBasicAuth(CONFIG['conductor_token'], 'unused'),
                headers=headers,
                params=params,
                data=data)
        )


        logger.debug('response.status_code: %s', response.status_code)
        # logger.debug('response.text is: %s', response.text)
        return response.text, response.status_code
