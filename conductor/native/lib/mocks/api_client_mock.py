"""Mock ApiClient for requests to get packages and projects.

ApiClientNoHost includes an incompatible version of Houdini (to my
current setup) and is useful for testing behaviour of software /
autodetect etc.
"""
import json
import os

PROJECTS_RESPONSE = {"data": [
    {"id": "123|deadpool", "name": "Deadpool",
     "status": "active"},
    {"id": "456|harrypotter", "name": "Harry Potter & the chamber of secrets",
     "status": "active"},
    {"id": "789|corelli", "name": "Captain Corelli's Mandolin",
     "status": "active"},
    {"id": "000|gwtw", "name": "Gone with the Wind",
     "status": "inactive"}
]}


def _read(fixture):
    filename = os.path.join(
        os.path.dirname(__file__),
        "..",
        "fixtures",
        fixture)
    with open(filename, 'r') as content:
        return [content.read(), 200]


class ApiClientMock(object):

    def make_request(self, **kw):
        path = kw.get("uri_path", "")

        print("Using mock %s call to %s" % (self.__class__.__name__, path))

        if path.startswith("api/v1/projects"):
            return [json.dumps(PROJECTS_RESPONSE), 200]

        if path.startswith("api/v1/ee/packages"):
            return _read(self.JSON)


class ApiClient(ApiClientMock):
    JSON = "sw_packages.json"


class ApiClientNoHost(ApiClientMock):
    JSON = "sw_packages_no_exact_host.json"
