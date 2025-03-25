from copy import deepcopy
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from metafold.workflows import Workflow
from urllib.parse import parse_qs, urlparse
import json
import pytest

default_dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

# Default sort order is descending by id
workflow_list = [
    {
        "id": "3",
        "jobs": ["1", "2"],
        "state": "success",
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "started": "Mon, 01 Jan 2024 00:00:00 GMT",
        "finished": "Mon, 01 Jan 2024 00:00:00 GMT",
        "definition": "...",
        "project_id": "1",
    },
    {
        "id": "2",
        "jobs": ["1", "2"],
        "state": "started",
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "started": "Mon, 01 Jan 2024 00:00:00 GMT",
        "finished": "Mon, 01 Jan 2024 00:00:00 GMT",
        "definition": "...",
        "project_id": "1",
    },
    {
        "id": "1",
        "jobs": ["1", "2"],
        "state": "success",
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "started": "Mon, 01 Jan 2024 00:00:00 GMT",
        "finished": "Mon, 01 Jan 2024 00:00:00 GMT",
        "definition": "...",
        "project_id": "1",
    },
]

new_workflow = {
    "id": "1",
    "jobs": ["1", "2"],
    "created": "Mon, 01 Jan 2024 00:00:00 GMT",
    "started": "Mon, 01 Jan 2024 00:00:00 GMT",
    "finished": "Mon, 01 Jan 2024 00:00:00 GMT",
    "definition": "foo",
    "project_id": "1",
}

poll_count: int = 0


class MockRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        params = parse_qs(u.query)
        if u.path == "/projects/1/workflows":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = workflow_list
            if params.get("sort") == ["id:1"]:
                payload = sorted(workflow_list, key=lambda p: p["id"])
            elif params.get("q") == ["state:started"]:
                payload = [p for p in workflow_list if p["state"] == "started"]
            self.wfile.write(json.dumps(payload).encode())
        elif u.path == "/projects/1/workflows/1":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = deepcopy(workflow_list[-1])
            self.wfile.write(json.dumps(payload).encode())
        elif u.path == "/projects/1/workflows/1/status":
            global poll_count
            poll_count += 1
            if poll_count < 3:
                self.send_response(HTTPStatus.ACCEPTED)
                payload = deepcopy(new_workflow)
                payload["state"] = "started"
            else:
                self.send_response(HTTPStatus.CREATED)
                payload = deepcopy(new_workflow)
                payload["state"] = "success"
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if self.path == "/projects/1/workflows":
            self.send_response(HTTPStatus.ACCEPTED)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = deepcopy(new_workflow)
            payload.update({
                "state": "pending",
                "link": "http://localhost:8000/projects/1/workflows/1/status",
            })
            self.wfile.write(json.dumps(payload).encode())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


@pytest.fixture(scope="module")
def request_handler():
    return MockRequestHandler


def test_list_workflows(client):
    workflows = client.workflows.list()
    assert [w.id for w in workflows] == ["3", "2", "1"]


def test_list_workflows_sorted(client):
    workflows = client.workflows.list(sort="id:1")
    assert [w.id for w in workflows] == ["1", "2", "3"]


def test_list_workflows_filtered(client):
    workflows = client.workflows.list(q="state:started")
    assert all([w.state == "started" for w in workflows])


def test_get_workflow(client):
    w = client.workflows.get("1")
    assert w == Workflow(
        id="1",
        jobs=["1", "2"],
        state="success",
        created=default_dt,
        started=default_dt,
        finished=default_dt,
        definition="...",
        project_id="1",
    )


def test_run_workflow(client):
    definition = "foo"
    w = client.workflows.run(definition)
    assert w == Workflow(
        id="1",
        jobs=["1", "2"],
        state="success",
        created=default_dt,
        started=default_dt,
        finished=default_dt,
        definition=definition,
        project_id="1",
    )
