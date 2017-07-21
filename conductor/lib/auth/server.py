import os
import inspect
import json
import mimetypes
import urlparse
import time

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

keep_running = True
credentials_file = ""
REQUEST_TIMEOUT = 1  # number of seconds we're waiting per request
SESSION_TIMEOUT = 30  # number of seconds we're waiting for user to get credentials


class Handler(BaseHTTPRequestHandler):
    def _set_headers(self, path=''):
        self.send_response(200)
        self.send_header('Content-type', mimetypes.guess_type(path)[0])
        self.end_headers()

    def _write_credentials(self, credentials):
        print ("Writing credentials to %s" % credentials_file)
        if not os.path.exists(os.path.dirname(credentials_file)):
            print("Creating creds directory %s" % os.path.dirname(credentials_file))
            os.mkdir(os.path.dirname(credentials_file))
        with open(credentials_file, 'w') as token_file:
            token_file.write(json.dumps(credentials))

    def do_POST(self):
        self._set_headers()

    def do_GET(self):
        #  Handle arg string
        self._set_headers()
        print ("Got a response!")
        url_args = urlparse.parse_qs(urlparse.urlsplit(self.path).query)
        if 'access_token' not in url_args:
            return

        credentials_dict = {
            "access_token": url_args['access_token'][0],
            "token_type": "Bearer",
            "expiration": int(time.time()) + int(url_args['expires_in'][0]),
            "scope": url_args['scope']
        }
        self._write_credentials(credentials_dict)
        self.wfile.write("Please close your browser!")
        global keep_running
        keep_running = False
        return

    @property
    def web_root(self):
        return os.path.sep.join((os.path.dirname(os.path.abspath(inspect.stack()[0][1])), 'resources'))


def run(server_class=HTTPServer, handler_class=Handler, port=8085, creds_file=None):
    global credentials_file
    credentials_file = creds_file
    server_address = ('localhost', port)
    httpd = server_class(server_address, handler_class)
    httpd.timeout = REQUEST_TIMEOUT
    timeout = time.time() + SESSION_TIMEOUT
    while time.time() < timeout and keep_running:
        httpd.handle_request()
