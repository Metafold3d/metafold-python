from attrs import field, frozen
from datetime import datetime
from enum import Enum
from metafold.api import asdatetime, asdict
from metafold.client import Client
from metafold.func_types import Graph
from requests import Response
from typing import Any, Optional, Union


class Access(Enum):
    """Project access scope.

    Attributes:
        PRIVATE: Project is private to owner.
        PUBLIC: Project may be accessed by unauthenticated users.
    """
    PRIVATE = "private"
    PUBLIC = "public"


def check_access(a: str) -> Access:
    if a.upper() not in Access.__dict__:
        raise ValueError("Expected 'private' or 'public'")
    return Access[a.upper()]


@frozen(kw_only=True)
class Project:
    """Project resource.

    Attributes:
        id: Project ID.
        user: Project user ID.
        name: Project name.
        access: Project access.
        created: Project creation datetime.
        modified: Project last modified datetime.
        thumbnail: URL to project thumbnail.
        project: Arbitrary project data.
        graph: Project graph data.
    """
    id: str
    user: str
    name: str
    access: Access = field(converter=check_access)
    created: datetime = field(converter=asdatetime)
    modified: datetime = field(converter=asdatetime)
    thumbnail: Optional[str] = None
    project: Optional[dict[str, Any]] = None
    graph: Optional[Graph] = None


class ProjectsEndpoint:
    """Metafold projects endpoint."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def list(self, sort: Optional[str] = None, q: Optional[str] = None) -> list[Project]:
        """List projects.

        Args:
            sort: Sort string. For details on syntax see the Metafold API docs.
                Supported sorting fields are: "id", "user", "name", "created", and
                "modified".
            q: Query string. For details on syntax see the Metafold API docs.
                Supported search fields are: "id", "user", and "name".

        Returns:
            List of project resources.
        """
        payload = asdict(sort=sort, q=q)
        r: Response = self._client.get("/projects", params=payload)
        return [Project(**a) for a in r.json()]

    def get(self, id: Optional[str] = None) -> Project:
        """Get an project.

        Args:
            id: Override ID of project to get. Defaults to client project ID.

        Returns:
            Project resource.
        """
        id = self._client.project_id(id)
        url = f"/projects/{id}"
        r: Response = self._client.get(url)
        return Project(**r.json())

    def create(
        self, name: str,
        access: Union[Access, str] = Access.PRIVATE,
        data: Optional[dict[str, Any]] = None,
    ) -> Project:
        """Create a project.

        Args:
            name: Project name.
            access: Project access. By default projects are private.
            data: Optional project data. This parameter accepts arbitrary
                JSON-serializable data. Helpful for tracking application state.

        Returns:
            Project resource.
        """
        if isinstance(access, str):
            access = check_access(access)
        payload = asdict(name=name, access=access.value, project=data)
        r: Response = self._client.post("/projects", json=payload)
        return Project(**r.json())

    def duplicate(
        self, id: str, name: str,
        access: Union[Access, str] = Access.PRIVATE,
    ) -> Project:
        """Duplicate a project.

        Args:
            id: Project to duplicate.
            name: New project name.
            access: New project access. By default projects are private.

        Returns:
            Project resource.
        """
        if isinstance(access, str):
            access = check_access(access)
        payload = asdict(source=id, name=name, access=access.value)
        r: Response = self._client.post("/projects", json=payload)
        return Project(**r.json())

    def update(
        self,
        id: Optional[str] = None,
        name: Optional[str] = None,
        access: Optional[Union[Access, str]] = None,
        data: Optional[dict[str, Any]] = None,
        graph: Optional[Graph] = None,
    ) -> Project:
        """Update a project.

        Args:
            id: Override ID of project to update. Defaults to client project ID.
            name: Optional project name.
            access: Optional project access.
            data: Optional project data. This parameter accepts arbitrary
                JSON-serializable data. Helpful for tracking application state.
            graph: Optional shape JSON.

        Returns:
            Updated project resource.
        """
        if access and isinstance(access, str):
            access = check_access(access)
        id = self._client.project_id(id)
        url = f"/projects/{id}"
        payload = asdict(name=name, project=data, graph=graph)
        # Access is optional, but we also need to cast to str
        if isinstance(access, Access):
            payload["access"] = access.value
        r: Response = self._client.patch(url, json=payload)
        return Project(**r.json())

    def delete(self, id: str) -> None:
        """Delete an project.

        Args:
            id: Override ID of project to update. Defaults to client project ID.
        """
        id = self._client.project_id(id)
        url = f"/projects/{id}"
        self._client.delete(url)
