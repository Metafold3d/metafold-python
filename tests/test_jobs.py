from copy import deepcopy
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from metafold.assets import Asset
from metafold.jobs import Job
from urllib.parse import parse_qs, urlparse
import json
import pytest

default_dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

asset_json = {
    "id": "1",
    "filename": "f763df409e79eb1c.bin",
    "size": 16777216,
    "checksum": "sha256:6310a5951d58eb3e0fdd8c8767c606615552899e65019cb1582508a7c7bfec39",
    "created": "Mon, 01 Jan 2024 00:00:00 GMT",
    "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
}

asset_obj = Asset(
    id="1",
    filename="f763df409e79eb1c.bin",
    size=16777216,
    checksum="sha256:6310a5951d58eb3e0fdd8c8767c606615552899e65019cb1582508a7c7bfec39",
    created=default_dt,
    modified=default_dt,
)

# Default sort order is descending by id
job_list = [
    {
        "id": "3",
        "name": "bar",
        "type": "evaluate_graph",
        "parameters": {
            "graph": None,
        },
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "state": "success",
        "assets": [asset_json],
        "meta": None,
    },
    {
        "id": "2",
        "name": "foo",
        "type": "evaluate_graph",
        "parameters": {
            "graph": None,
        },
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "state": "success",
        "assets": [asset_json],
        "meta": None,
    },
    {
        "id": "1",
        "name": "foo",
        "type": "evaluate_graph",
        "parameters": {
            "graph": None,
        },
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "state": "success",
        "assets": [asset_json],
        "meta": None,
    },
]

new_job = {
    "id": "1",
    "name": "My Job",
    "type": "test_job",
    "parameters": {
        "foo": 1,
        "bar": "a",
        "baz": [2, "b"],
    },
    "created": "Mon, 01 Jan 2024 00:00:00 GMT",
    "assets": [],
    "meta": None,
}

poll_count: int = 0


class MockRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        params = parse_qs(u.query)
        match u.path:
            case "/projects/1/jobs":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                payload = job_list
                if params.get("sort") == ["id:1"]:
                    payload = sorted(job_list, key=lambda p: p["id"])
                elif params.get("q") == ["name:foo"]:
                    payload = [p for p in job_list if p["name"] == "foo"]
                self.wfile.write(json.dumps(payload).encode())
            case "/projects/1/jobs/1":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                payload = job_list[-1]
                self.wfile.write(json.dumps(payload).encode())
            case "/projects/1/jobs/1/status":
                global poll_count
                poll_count += 1
                if poll_count < 3:
                    self.send_response(HTTPStatus.ACCEPTED)
                    payload = deepcopy(new_job)
                    payload["state"] = "started"
                else:
                    self.send_response(HTTPStatus.OK)
                    payload = deepcopy(new_job)
                    payload.update({
                        "state": "success",
                        "assets": [asset_json],
                    })
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())
            case _:
                self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        match self.path:
            case "/projects/1/jobs":
                self.send_response(HTTPStatus.ACCEPTED)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                payload = deepcopy(new_job)
                payload.update({
                    "state": "pending",
                    "link": "http://localhost:8000/projects/1/jobs/1/status",
                })
                self.wfile.write(json.dumps(payload).encode())
            case _:
                self.send_error(HTTPStatus.NOT_FOUND)

    def do_PATCH(self):
        match self.path:
            case "/projects/1/jobs/1":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                payload = deepcopy(job_list[-1])
                payload["name"] = "baz"
                self.wfile.write(json.dumps(payload).encode())
            case _:
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
        parameters={
            "graph": None,
        },
        created=default_dt,
        state="success",
        assets=[asset_obj],
        meta=None,
    )


def test_run_job(client):
    params = {
        "foo": 1,
        "bar": "a",
        "baz": [2, "b"],
    }
    j = client.jobs.run("test_job", params, name="My Job")
    assert j == Job(
        id="1",
        name="My Job",
        type="test_job",
        parameters=params,
        created=default_dt,
        state="success",
        assets=[asset_obj],
        meta=None,
    )


def test_update_job(client):
    j = client.jobs.update("1", name="baz")
    assert j.name == "baz"
