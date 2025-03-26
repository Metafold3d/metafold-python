from attrs import field, frozen
from datetime import datetime
from metafold.api import asdatetime, asdict
from metafold.client import Client
from os import PathLike
from requests import Response
from typing import IO, Optional, Union
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
        project_id: Project ID.
        job_id: Job ID.
    """
    id: str
    filename: str
    size: int
    checksum: str
    created: datetime = field(converter=asdatetime)
    modified: datetime = field(converter=asdatetime)
    project_id: str
    job_id: Optional[str] = None


class AssetsEndpoint:
    """Metafold assets endpoint."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def list(
        self,
        sort: Optional[str] = None,
        q: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> list[Asset]:
        """List assets.

        Args:
            sort: Sort string. For details on syntax see the Metafold API docs.
                Supported sorting fields are: "id", "filename", "size", "created", or
                "modified".
            q: Query string. For details on syntax see the Metafold API docs.
                Supported search fields are: "id" and "filename".
            project_id: Asset project ID.

        Returns:
            List of asset resources.
        """
        project_id = self._client.project_id(project_id)
        url = f"/projects/{project_id}/assets"
        payload = asdict(sort=sort, q=q)
        r: Response = self._client.get(url, params=payload)
        return [Asset(**a) for a in r.json()]

    def get(self, asset_id: str, project_id: Optional[str] = None) -> Asset:
        """Get an asset.

        Args:
            asset_id: ID of asset to get.
            project_id: Asset project ID.

        Returns:
            Asset resource.
        """
        project_id = self._client.project_id(project_id)
        url = f"/projects/{project_id}/assets/{asset_id}"
        r: Response = self._client.get(url)
        return Asset(**r.json())

    def download_file(
        self, asset_id: str, path: Union[str, PathLike],
        project_id: Optional[str] = None,
    ):
        """Download an asset.

        Args:
            asset_id: ID of asset to download.
            path: Path to downloaded file.
            project_id: Asset project ID.
        """
        project_id = self._client.project_id(project_id)
        url = f"/projects/{project_id}/assets/{asset_id}"
        r: Response = self._client.get(url, params={"download": "true"})
        r = requests.get(r.json()["link"], stream=True)
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):  # 64 KiB
                f.write(chunk)

    def create(
        self, f: Union[str, bytes, PathLike, IO[bytes]],
        project_id: Optional[str] = None,
    ) -> Asset:
        """Upload an asset.

        Args:
            f: File-like object (opened in binary mode) or path to file on disk.
            project_id: Asset project ID.

        Returns:
            Asset resource.
        """
        project_id = self._client.project_id(project_id)
        fp: IO[bytes] = _open_file(f)
        try:
            url = f"/projects/{project_id}/assets"
            r: Response = self._client.post(url, files={"file": fp})
        finally:
            fp.close()
        return Asset(**r.json())

    def delete(self, asset_id: str, project_id: Optional[str] = None) -> None:
        """Delete an asset.

        Args:
            asset_id: ID of asset to delete.
            project_id: Asset project ID.
        """
        project_id = self._client.project_id(project_id)
        url = f"/projects/{project_id}/assets/{asset_id}"
        self._client.delete(url)


def _open_file(f: Union[str, bytes, PathLike, IO[bytes]]) -> IO[bytes]:
    if isinstance(f, (str, bytes, PathLike)):
        return open(f, "rb")
    return f
