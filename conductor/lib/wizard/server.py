import os
import inspect
import json
import yaml
import errno

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

keep_running = True

class Handler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
    def _write_config_files(self,config):
        try:
            os.makedirs(self.config_dir)
        except OSError as e:
            if e.errno == errno.EEXIST and os.path.isdir(self.config_dir):
                pass
            else:
                raise
            
        with open(os.path.join(self.config_dir,"CONDUCTOR_TOKEN"),'w') as token_file:
            token_file.write(config['token'])
        
        with open (os.environ['CONDUCTOR_CONFIG'],'w') as config_file:
            config_file.write(yaml.dump(
                {
                    'account':str(config['account']),
                    'token_path':os.path.join(self.config_dir,"CONDUCTOR_TOKEN")
                },
                default_flow_style=False)
            )
            
        
    def do_POST(self):
        self._set_headers()
        self._write_config_files(json.loads(self.rfile.read(int(self.headers['Content-Length']))))

    def do_GET(self):
        path = os.path.sep.join((self.web_root,self.path))
        try:
            with open(path,'r') as src:
                content = src.read()
        except IOError:
            self.send_response(404)
            return

        self._set_headers()
        self.wfile.write(content)
        if 'finish' in self.path:
            global keep_running
            keep_running = False
        
    @property
    def web_root(self):
        return os.path.sep.join((os.path.dirname(os.path.abspath(inspect.stack()[0][1])),'resources'))
    
    @property
    def config_dir(self):
        return os.path.dirname(os.path.abspath(os.environ['CONDUCTOR_CONFIG']))

def run(server_class=HTTPServer, handler_class=Handler, port=8085):
    server_address = ('localhost', port)
    httpd = server_class(server_address, handler_class)
    while keep_running:
        httpd.handle_request()