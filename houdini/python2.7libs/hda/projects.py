from conductor.lib import api_client
import json
import submit


def active_projects():
    """Get active projects from the server.

    If there is a problem of any kind (exception, empty
    list) just return the single object to signify not set,
    otherwise prepend "not set to the list of projects". In
    this way we can populate the menu with at least one item
    and disable submit button if not set, rather than
    interrupting flow with an error.

    """
    notset = [{"id": "notset", "name": "- Not set -"}]
    api = api_client.ApiClient()

    response, response_code = api.make_request(
        uri_path='api/v1/projects/', verb="GET", raise_on_error=False, use_api_key=True)
    if response_code not in [200]:
        return notset

    projects = json.loads(response).get("data")
    if not projects:
        return notset

    projects = [{"id": project["id"], "name": project["name"]}
                for project in projects if (project.get("status") == "active")]
    if not projects:
        return notset

    projects += notset
    return sorted(projects, key=lambda project: project["name"].lower())


def fetch(node):
    """Fetch the list of projects and store on projects param. If we don't do
    this, and instead fetch every time the menu is accessed, there is an
    unacceptable delay. If we rebuild this list, and for some reason the
    selected project is not in it, then set selected to the.

    first item in the list, which will be the - Not set - item.

    """
    projects = active_projects()
    node.parm('projects').set(json.dumps(projects))

    selected = node.parm('project').eval()
    if selected not in (project["id"] for project in projects):
        node.parm('project').set(projects[0]["id"])

    return projects


def populate_menu(node):
    """Populate project menu.

    Get list from the projects param where they are cached.
    If there are none, which can only happen on create, then
    fetch them from the server.

    """
    projects = json.loads(node.parm('projects').eval())
    if not bool(projects):
        projects = fetch(node)
    res = [k for i in projects for k in (i["id"], i["name"])]
    return res


def has_valid_project(node):
    """Make sure the project is valid.

    This helps determine if the submit button should be
    enabled.

    """
    projects = json.loads(node.parm('projects').eval())
    selected = node.parm('project').eval()
    if selected == "notset" or selected not in (
            project["id"] for project in projects):
        return False
    return True


def select(node, **kw):
    """When user chooses a new project, update the submit button."""
    submit.update_button_state(node)
