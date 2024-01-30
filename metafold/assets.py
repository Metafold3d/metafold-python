from attrs import field, frozen
from datetime import datetime
from metafold.api import asdatetime, asdict
from metafold.client import Client
from os import PathLike
from requests import Response
from typing import IO, Optional
import requests


@frozen(kw_only=True)
class Asset:
    """Asset resource.

    Attributes:
        id: Asset ID.
        filename: Asset filename.
        size: File size in bytes.
        checksum: File checksum.
        created: Asset creation datetime.
        modified: Asset last modified datetime.
    """
    id: str
    filename: str
    size: int
    checksum: str
    created: datetime = field(converter=asdatetime)
    modified: datetime = field(converter=asdatetime)


class AssetsEndpoint:
    """Metafold assets endpoint."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def list(self, sort: Optional[str] = None, q: Optional[str] = None) -> list[Asset]:
        """List assets.

        Args:
            sort: Sort string. For details on syntax see the Metafold API docs.
                Supported sorting fields are: "id", "filename", "size", "created", or
                "modified".
            q: Query string. For details on syntax see the Metafold API docs.
                Supported search fields are: "id" and "filename".

        Returns:
            List of asset resources.
        """
        url = f"/projects/{self._client.project_id}/assets"
        payload = asdict(sort=sort, q=q)
        r: Response = self._client.get(url, params=payload)
        return [Asset(**a) for a in r.json()]

    def get(self, id: str) -> Asset:
        """Get an asset.

        Args:
            id: ID of asset to get.

        Returns:
            Asset resource.
        """
        url = f"/projects/{self._client.project_id}/assets/{id}"
        r: Response = self._client.get(url)
        return Asset(**r.json())

    def download_file(self, id: str, path: str | PathLike):
        """Download an asset.

        Args:
            id: ID of asset to download.
            path: Path to downloaded file.
        """
        url = f"/projects/{self._client.project_id}/assets/{id}"
        r: Response = self._client.get(url, params={"download": "true"})
        r = requests.get(r.json()["link"], stream=True)
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):  # 64 KiB
                f.write(chunk)

    def create(self, f: str | bytes | PathLike | IO[bytes]) -> Asset:
        """Upload an asset.

        Args:
            f: File-like object (opened in binary mode) or path to file on disk.

        Returns:
            Asset resource.
        """
        fp: IO[bytes] = _open_file(f)
        try:
            url = f"/projects/{self._client.project_id}/assets"
            r: Response = self._client.post(url, files={"file": fp})
        finally:
            fp.close()
        return Asset(**r.json())

    def update(self, id: str, f: str | bytes | PathLike | IO[bytes]) -> Asset:
        """Update an asset.

        Args:
            id: ID of asset to update.
            f: File-like object (opened in binary mode) or path to file on disk.

        Returns:
            Updated asset resource.
        """
        fp: IO[bytes] = _open_file(f)
        try:
            url = f"/projects/{self._client.project_id}/assets/{id}"
            r: Response = self._client.patch(url, files={"file": fp})
        finally:
            fp.close()
        return Asset(**r.json())

    def delete(self, id: str) -> None:
        """Delete an asset.

        Args:
            id: ID of asset to delete.
        """
        url = f"/projects/{self._client.project_id}/assets/{id}"
        self._client.delete(url)


def _open_file(f: str | bytes | PathLike | IO[bytes]) -> IO[bytes]:
    if isinstance(f, str | bytes | PathLike):
        return open(f, "rb")
    return f
