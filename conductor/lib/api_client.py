import urllib
import urllib2
import urlparse

import conductor, conductor.setup

from conductor.setup import *
from conductor.lib import common

class ApiClient():
    def __init__(self):
        logger.debug('')
        self.authorize_urllib()

    def get_token(self):
        userpass = "%s:unused" % CONFIG['conductor_token']
        return userpass

    def authorize_urllib(self):
        '''
        This is crazy magic that's apparently ok
        '''
        token = self.get_token()
        password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(None, CONFIG['url'], token.split(':')[0], 'unused')
        auth = urllib2.HTTPBasicAuthHandler(password_manager)
        opener = urllib2.build_opener(auth)
        urllib2.install_opener(opener)


    def make_request(self, uri_path="/", headers=None, params=None, data=None, verb=None):
        '''
        verb: PUT, POST, GET, DELETE, HEAD
        '''
        # TODO: set Content Type to json if data arg
        if not headers:
            headers = {'Content-Type':'application/json'}
        logger.debug('headers are: %s', headers)

        # Construct URL
        print "CONFIG['url'] is %s" % CONFIG['url']
        print "uri_path is %s" % uri_path
        conductor_url = urlparse.urljoin(CONFIG['url'], uri_path)
        logger.debug('conductor_url: %s', conductor_url)
        if params:
            conductor_url += '?'
            conductor_url += urllib.urlencode(params)
        logger.debug('conductor_url is %s', conductor_url)

        req = urllib2.Request(conductor_url, headers=headers, data=data)
        if verb:
            req.get_method = lambda: verb
        logger.debug('request is %s', req)

        logger.debug('trying to connect to app')
        handler = common.retry(lambda: urllib2.urlopen(req))
        response_string = handler.read()
        response_code = handler.getcode()
        logger.debug('response_code: %s', response_code)
        logger.debug('response_string is: %s', response_string)
        return response_string, response_code
