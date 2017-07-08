import webbrowser
import server

def run(creds_file):
    if webbrowser.open("https://dashboard.dev-conductortech.com/api/oauth_jwt?redirect_uri=http://localhost:8085/index.html&scope=user&response_type=client_token", new=1, autoraise=True):
        server.run(port=8085, creds_file=creds_file)
    else:
        raise RuntimeError ("Unable to open web browser.  Please contact Conductor support for help configuring Conductor Client")