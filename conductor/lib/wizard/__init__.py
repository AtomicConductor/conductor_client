import webbrowser
import server
import os

def run():
    if not 'CONDUCTOR_CONFIG' in os.environ:
        raise RuntimeError("CONDUCTOR_CONFIG is not set in the environment. Please contact Conductor support for help configuring Conductor Client")
    
    if webbrowser.open('http://localhost:8085/index.html', new=0, autoraise=True):
        server.run(port=8085)
    else:
        raise RuntimeError ("Unable to open web browser.  Please contact Conductor support for help configuring Conductor Client")