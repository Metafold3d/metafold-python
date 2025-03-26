from copy import deepcopy
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from metafold.assets import Asset
from pathlib import Path
from requests_toolbelt import MultipartDecoder
from urllib.parse import parse_qs, urlparse
import filecmp
import json
import pytest

test_root = Path(__file__).parent
test_file = test_root / "test.png"

default_dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

# Default sort order is descending by id
asset_list = [
    {
        "id": "3",
        "filename": "2c7386e81b6d2ed4.bin",
        "size": 16777216,
        "checksum": "sha256:b5bb9d8014a0f9b1d61e21e796d78dccdf1352f23cd32812f4850b878ae4944c",
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        "project_id": "1",
        "job_id": None,
    },
    {
        "id": "2",
        "filename": "f763df409e79eb1c.bin",
        "size": 16777216,
        "checksum": "sha256:6310a5951d58eb3e0fdd8c8767c606615552899e65019cb1582508a7c7bfec39",
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        "project_id": "1",
        "job_id": None,
    },
    {
        "id": "1",
        "filename": "f763df409e79eb1c.bin",
        "size": 16777216,
        "checksum": "sha256:6310a5951d58eb3e0fdd8c8767c606615552899e65019cb1582508a7c7bfec39",
        "created": "Mon, 01 Jan 2024 00:00:00 GMT",
        "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        "project_id": "1",
        "job_id": None,
    },
]

new_asset = {
    "id": "1",
    "filename": "test.png",
    "size": 67,
    "checksum": "sha256:089ad5bf4831b6758e9907db43bc5ebba2e9248a9929dad6132c49932e538278",
    "created": "Mon, 01 Jan 2024 00:00:00 GMT",
    "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
    "project_id": "1",
    "job_id": None,
}


class MockRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        params = parse_qs(u.query)
        if u.path == "/projects/1/assets":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = asset_list
            if params.get("sort") == ["id:1"]:
                payload = sorted(asset_list, key=lambda p: p["id"])
            elif params.get("q") == ["filename:f763df409e79eb1c.bin"]:
                payload = [p for p in asset_list if p["filename"] == "f763df409e79eb1c.bin"]
            self.wfile.write(json.dumps(payload).encode())
        elif u.path == "/projects/1/assets/1":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = deepcopy(asset_list[-1])
            if params.get("download") == ["true"]:
                payload["link"] = "http://localhost:8000/download?filename=f763df409e79eb1c.bin"
            self.wfile.write(json.dumps(payload).encode())
        elif u.path == "/download":
            self.send_response(HTTPStatus.OK)
            self.end_headers()
            with open(test_file, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if self.path == "/projects/1/assets":
            self.send_response(HTTPStatus.CREATED)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self._assert_file()
            self.wfile.write(json.dumps(new_asset).encode())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_PATCH(self):
        if self.path == "/projects/1/assets/1":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self._assert_file()
            self.wfile.write(json.dumps(new_asset).encode())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        if self.path == "/projects/1/assets/1":
            self.send_response(HTTPStatus.OK)
            self.end_headers()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _assert_file(self):
        length = self.headers.get("Content-Length")
        content_type = self.headers.get("Content-Type")
        content = self.rfile.read(int(length))
        decoder = MultipartDecoder(content, content_type)
        file = decoder.parts[0].content
        with open(test_file, "rb") as f:
            assert file == f.read()


@pytest.fixture(scope="module")
def request_handler():
    return MockRequestHandler


def test_list_assets(client):
    assets = client.assets.list()
    assert [a.id for a in assets] == ["3", "2", "1"]


def test_list_assets_sorted(client):
    assets = client.assets.list(sort="id:1")
    assert [a.id for a in assets] == ["1", "2", "3"]


def test_list_assets_filtered(client):
    assets = client.assets.list(q="filename:f763df409e79eb1c.bin")
    assert all([a.filename == "f763df409e79eb1c.bin" for a in assets])


def test_get_asset(client):
    a = client.assets.get("1")
    assert a == Asset(
        id="1",
        filename="f763df409e79eb1c.bin",
        size=16777216,
        checksum="sha256:6310a5951d58eb3e0fdd8c8767c606615552899e65019cb1582508a7c7bfec39",
        created=default_dt,
        modified=default_dt,
        project_id="1",
        job_id=None,
    )


def test_download_asset(client, tmp_path):
    path = tmp_path / "test.png"
    client.assets.download_file("1", path)
    assert filecmp.cmp(path, test_file, shallow=False)


def test_create_asset(client):
    with open(test_file, "rb") as f:
        a = client.assets.create(f)
    assert a == Asset(
        id="1",
        filename="test.png",
        size=67,
        checksum="sha256:089ad5bf4831b6758e9907db43bc5ebba2e9248a9929dad6132c49932e538278",
        created=default_dt,
        modified=default_dt,
        project_id="1",
        job_id=None,
    )


def test_delete_asset(client):
    # FIXME: Assert something
    client.assets.delete("1")
