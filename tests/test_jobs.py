from copy import deepcopy
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from metafold.assets import Asset
from metafold.jobs import Job, IO
from urllib.parse import parse_qs, urlparse
import json
import pytest

default_dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

default_params = {
    "foo": "...",
    "bar": "...",
}

asset_json = {
    "id": "1",
    "filename": "f763df409e79eb1c.bin",
    "size": 16777216,
    "checksum": "sha256:6310a5951d58eb3e0fdd8c8767c606615552899e65019cb1582508a7c7bfec39",
    "created": "Mon, 01 Jan 2024 00:00:00 GMT",
    "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
    "project_id": "1",
}

asset_obj = Asset(
    id="1",
    filename="f763df409e79eb1c.bin",
    size=16777216,
    checksum="sha256:6310a5951d58eb3e0fdd8c8767c606615552899e65019cb1582508a7c7bfec39",
    created=default_dt,
    modified=default_dt,
    project_id="1",
)

# Default sort order is descending by id
job_list = [
    {
        "id": "3",
        "name": "bar",
        "type": "evaluate_graph",
        "state": "success",
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "started": "Mon, 01 Jan 2024 00:00:00 GMT",
        "finished": "Mon, 01 Jan 2024 00:00:00 GMT",
        "error": None,
        "inputs": {
            "params": default_params,
        },
        "outputs": {
            "params": None,
        },
        "needs": [],
        "project_id": "1",
        "workflow_id": None,
        "parameters": default_params,
        "meta": None,
    },
    {
        "id": "2",
        "name": "foo",
        "type": "evaluate_graph",
        "state": "success",
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "started": "Mon, 01 Jan 2024 00:00:00 GMT",
        "finished": "Mon, 01 Jan 2024 00:00:00 GMT",
        "error": None,
        "inputs": {
            "params": default_params,
        },
        "outputs": {
            "params": None,
        },
        "needs": [],
        "project_id": "1",
        "workflow_id": None,
        "parameters": default_params,
        "meta": None,
    },
    {
        "id": "1",
        "name": "foo",
        "type": "evaluate_graph",
        "state": "success",
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "started": "Mon, 01 Jan 2024 00:00:00 GMT",
        "finished": "Mon, 01 Jan 2024 00:00:00 GMT",
        "error": None,
        "inputs": {
            "params": default_params,
        },
        "outputs": {
            "params": None,
        },
        "needs": [],
        "project_id": "1",
        "workflow_id": None,
        "parameters": default_params,
        "meta": None,
    },
]

new_job = {
    "id": "1",
    "name": "My Job",
    "type": "test_job",
    "created": "Mon, 01 Jan 2024 00:00:00 GMT",
    "started": "Mon, 01 Jan 2024 00:00:00 GMT",
    "finished": "Mon, 01 Jan 2024 00:00:00 GMT",
    "error": None,
    "inputs": {
        "params": {
            "foo": "1",
            "bar": "a",
            "baz": "[2, \"b\"]",
        },
    },
    "outputs": {
        "params": None,
    },
    "needs": [],
    "project_id": "1",
    "workflow_id": None,
    "assets": [],
    "parameters": {
        "foo": "1",
        "bar": "a",
        "baz": "[2, \"b\"]",
    },
    "meta": None,
}

poll_count: int = 0


class MockRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        params = parse_qs(u.query)
        if u.path == "/projects/1/jobs":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = job_list
            if params.get("sort") == ["id:1"]:
                payload = sorted(job_list, key=lambda p: p["id"])
            elif params.get("q") == ["name:foo"]:
                payload = [p for p in job_list if p["name"] == "foo"]
            self.wfile.write(json.dumps(payload).encode())
        elif u.path == "/projects/1/jobs/1":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = deepcopy(job_list[-1])
            payload["assets"] = [asset_json]
            self.wfile.write(json.dumps(payload).encode())
        elif u.path == "/projects/1/jobs/1/status":
            global poll_count
            poll_count += 1
            if poll_count < 3:
                self.send_response(HTTPStatus.ACCEPTED)
                payload = deepcopy(new_job)
                payload["state"] = "started"
            else:
                self.send_response(HTTPStatus.CREATED)
                payload = deepcopy(new_job)
                payload.update({
                    "state": "success",
                    "assets": [asset_json],
                })
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if self.path == "/projects/1/jobs":
            self.send_response(HTTPStatus.ACCEPTED)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = deepcopy(new_job)
            payload.update({
                "state": "pending",
                "link": "http://localhost:8000/projects/1/jobs/1/status",
            })
            self.wfile.write(json.dumps(payload).encode())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_PATCH(self):
        if self.path == "/projects/1/jobs/1":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = deepcopy(job_list[-1])
            payload.update({
                "name": "baz",
                "assets": [asset_json],
            })
            self.wfile.write(json.dumps(payload).encode())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


@pytest.fixture(scope="module")
def request_handler():
    return MockRequestHandler


def test_list_jobs(client):
    jobs = client.jobs.list()
    assert [j.id for j in jobs] == ["3", "2", "1"]


def test_list_jobs_sorted(client):
    jobs = client.jobs.list(sort="id:1")
    assert [j.id for j in jobs] == ["1", "2", "3"]


def test_list_jobs_filtered(client):
    jobs = client.jobs.list(q="name:foo")
    assert all([j.name == "foo" for j in jobs])


def test_get_job(client):
    j = client.jobs.get("1")
    assert j == Job(
        id="1",
        name="foo",
        type="evaluate_graph",
        state="success",
        created=default_dt,
        started=default_dt,
        finished=default_dt,
        error=None,
        inputs=IO(params=default_params),
        outputs=IO(),
        needs=[],
        project_id="1",
        workflow_id=None,
        assets=[asset_obj],
        parameters=default_params,
        meta=None,
    )


def test_run_job(client):
    params = {
        "foo": "1",
        "bar": "a",
        "baz": "[2, \"b\"]",
    }
    j = client.jobs.run("test_job", params, name="My Job")
    assert j == Job(
        id="1",
        name="My Job",
        type="test_job",
        state="success",
        created=default_dt,
        started=default_dt,
        finished=default_dt,
        inputs=IO(params=params),
        outputs=IO(),
        needs=[],
        project_id="1",
        workflow_id=None,
        assets=[asset_obj],
        parameters=params,
        meta=None,
    )


def test_poll_job(client):
    params = {
        "foo": "1",
        "bar": "a",
        "baz": "[2, \"b\"]",
    }
    url = client.jobs.run_status("test_job", params, name="My Job")
    assert url == "http://localhost:8000/projects/1/jobs/1/status"

    r = client.jobs.poll(url)
    assert Job(**r.json()) == Job(
        id="1",
        name="My Job",
        type="test_job",
        state="success",
        created=default_dt,
        started=default_dt,
        finished=default_dt,
        inputs=IO(params=params),
        outputs=IO(),
        needs=[],
        project_id="1",
        workflow_id=None,
        assets=[asset_obj],
        parameters=params,
        meta=None,
    )


def test_update_job(client):
    j = client.jobs.update("1", name="baz")
    assert j.name == "baz"
