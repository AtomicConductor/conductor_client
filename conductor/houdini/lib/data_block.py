import json
from conductor.lib import common
from conductor.houdini.lib import software_data as swd

# Below are 2 mock versions of ApiClient - I made because my account was deleted
# on the weekend and I couldn't access Conductor. Also handy to have fast
# updates.
# from conductor.houdini.lib.mocks.api_client_mock import ApiClient
# from conductor.houdini.lib.mocks.api_client_mock import ApiClientNoHost as ApiClient

# Uncomment next line to use the real version of ApiClient
from conductor.lib.api_client  import ApiClient


def _projects():
    """Get active projects from the server.

    If there is a problem of any kind (exception, empty
    list) just return the single object to signify not set,
    otherwise prepend "not set to the list of projects". In
    this way we can populate the menu with at least one item
    and disable submit button(s) if not set, rather than
    interrupting flow with an error.
    """
    notset = [{"id": "notset", "name": "- Not set -"}]

    response, response_code = ApiClient().make_request(
        uri_path='api/v1/projects/', verb="GET",
        raise_on_error=False, use_api_key=True)

    if response_code not in [200]:
        return notset

    projects = json.loads(response).get("data")
    if not projects:
        return notset

    projects = [{"id": project["id"], "name": project["name"]}
                for project in projects if project.get("status") == "active"]
    if not projects:
        return notset

    projects += notset
    return sorted(projects, key=lambda project: project["name"].lower())


def _packages():
    """Get packages list from Conductor."""
    response, response_code = ApiClient().make_request(
        uri_path='api/v1/ee/packages',
        verb="GET", raise_on_error=False, use_api_key=True)
    if response_code not in [200]:
        return []

    return json.loads(response).get("data", [])
    # TODO - figure out best waty to deal with errors here.


class ConductorDataBlock:
    """Singleton to keep some common data accessible.

    We store the list of instance types, projects, and the
    package tree here. In theory, this data is fetched once
    and then all the job & submitter nodes have access to it.
    User can force an update, which might be handy if they
    started working when offline, and then need to get real
    before submitting.

    The **kw args are:
    force = fetch from conductor again
    product = the product filter to pass onto the package_tree.
    """
    instance = None

    class __ConductorDataBlock:
        def __init__(self, **kw):
            self.force_update(**kw)

        def force_update(self, **kw):
            self._projects = _projects()
            self._instance_types = common.get_conductor_instance_types()
            self._package_tree = swd.PackageTree(_packages(), **kw)

        def __str__(self):
            return repr(self)

        def projects(self):
            return self._projects

        def instance_types(self):
            return self._instance_types

        def package_tree(self):
            return self._package_tree

    def __init__(self, **kw):
        """Create a new datablock the first time only."""

        if not ConductorDataBlock.instance:
            ConductorDataBlock.instance = ConductorDataBlock.__ConductorDataBlock(
                **kw)

        if kw.get("force"):
            ConductorDataBlock.instance.force_update(**kw)

    def __getattr__(self, name):
        """Delegate method calls to the singleton."""
        return getattr(self.instance, name)
