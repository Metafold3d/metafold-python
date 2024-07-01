from copy import deepcopy
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from metafold.projects import Access, Project
from urllib.parse import parse_qs, urlparse
import json
import pytest

default_dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

# Default sort order is descending by id
project_list = [
    {
        "id": "3",
        "user": "1",
        "name": "Foo",
        "access": "public",
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        "thumbnail": None,
    },
    {
        "id": "2",
        "user": "1",
        "name": "My Project",
        "access": "private",
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        "thumbnail": None,
    },
    {
        "id": "1",
        "user": "1",
        "name": "My Project",
        "access": "private",
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        "thumbnail": None,
    },
]

new_project = {
    "id": "1",
    "user": "1",
    "name": "New Project",
    "access": "public",
    "created": "Mon, 01 Jan 2024 00:00:00 GMT",
    "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
    "thumbnail": None,
}


class MockRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        params = parse_qs(u.query)
        if u.path == "/projects":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = project_list
            if params.get("sort") == ["id:1"]:
                payload = sorted(project_list, key=lambda p: p["id"])
            elif params.get("q") == ['name:"My Project"']:
                payload = [p for p in project_list if p["name"] == "My Project"]
            self.wfile.write(json.dumps(payload).encode())
        elif u.path == "/projects/1":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = deepcopy(project_list[-1])
            self.wfile.write(json.dumps(payload).encode())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        params = self._parse_json()
        if self.path == "/projects":
            self.send_response(HTTPStatus.CREATED)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = deepcopy(new_project)
            if "source" in params:
                payload["id"] = "2"
            self.wfile.write(json.dumps(payload).encode())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_PATCH(self):
        if self.path == "/projects/1":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(new_project).encode())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        if self.path == "/projects/1":
            self.send_response(HTTPStatus.OK)
            self.end_headers()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _parse_json(self):
        length = self.headers.get("Content-Length")
        content = self.rfile.read(int(length))
        return json.loads(content)


@pytest.fixture(scope="module")
def request_handler():
    return MockRequestHandler


def test_list_projects(client):
    projects = client.projects.list()
    assert [p.id for p in projects] == ["3", "2", "1"]


def test_list_projects_sorted(client):
    projects = client.projects.list(sort="id:1")
    assert [p.id for p in projects] == ["1", "2", "3"]


def test_list_projects_filtered(client):
    projects = client.projects.list(q='name:"My Project"')
    assert all([p.name == "My Project" for p in projects])


def test_get_project(client):
    p = client.projects.get("1")
    assert p == Project(
        id="1",
        user="1",
        name="My Project",
        access="private",
        created=default_dt,
        modified=default_dt,
    )


def test_create_project(client):
    p = client.projects.create("New Project", access=Access.PUBLIC)
    assert p == Project(
        id="1",
        user="1",
        name="New Project",
        access="public",
        created=default_dt,
        modified=default_dt,
    )


def test_duplicate_project(client):
    p = client.projects.duplicate("1", "New Project", access=Access.PUBLIC)
    assert p == Project(
        id="2",
        user="1",
        name="New Project",
        access="public",
        created=default_dt,
        modified=default_dt,
    )


def test_update_project(client):
    p = client.projects.update("1", name="New Project", access=Access.PUBLIC)
    assert p == Project(
        id="1",
        user="1",
        name="New Project",
        access="public",
        created=default_dt,
        modified=default_dt,
    )


def test_delete_project(client):
    # FIXME: Assert something
    client.projects.delete("1")
