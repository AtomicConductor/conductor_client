"""Mock ApiClient for requests to get packages and projects.

ApiClientNoHost includes an incompatible version of Houdini
(to my curret setup) and is useful for testing behaviour of
software / autodetect etc.
"""
import os
import json


PROJECTS_RESPONSE = {"data": [
    {"id": "123|deadpool", "name": "Deadpool", "status": "active"},
    {"id": "456|harrypotter", "name": "Harry Potter & the chamber of secrets", "status": "active"},
    {"id": "789|corelli", "name": "Captain Corelli's Mandolin", "status": "active"},
    {"id": "000|gwtw", "name": "Gone with the Wind", "status": "inactive"}
]}


def _read(fixture):
    fn = os.path.join(os.path.dirname(__file__), "..", "fixtures", fixture)
    with open(fn, 'r') as content:
        return [content.read(), 200]


class ApiClient():
    def make_request(self, **kw):

        path = kw.get("uri_path", "")
        if kw.get("uri_path", "").startswith("api/v1/projects"):
            return [json.dumps(PROJECTS_RESPONSE), 200]

        if kw.get("uri_path", "").startswith("api/v1/ee/packages"):
            return _read("sw_packages.json")


class ApiClientNoHost():
    def make_request(self, **kw):

        if kw.get("uri_path", "").startswith("api/v1/projects"):
            return [json.dumps(PROJECTS_RESPONSE), 200]

        if kw.get("uri_path", "").startswith("api/v1/ee/packages"):
            return _read("sw_packages_no_exact_host.json")
