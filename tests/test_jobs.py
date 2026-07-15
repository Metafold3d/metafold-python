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
