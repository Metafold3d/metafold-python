from attrs import field, frozen
from datetime import datetime
from metafold.api import asdatetime, asdict, optional_datetime
from metafold.client import Client
from metafold.exceptions import PollTimeout
from requests import Response
from typing import Optional, Union


@frozen(kw_only=True)
class Workflow:
    """Workflow resource.

    Attributes:
        id: Workflow ID.
        state: Workflow state. May be one of: pending, started, success, failure, or
            canceled.
        created: Workflow creation datetime.
        started: Workflow started datetime.
        finished: Workflow finished datetime.
        definition: Workflow definition string.
        project_id: Project ID.
    """
    id: str
    jobs: list[str] = field(factory=list)
    state: str
    created: datetime = field(converter=asdatetime)
    started: Optional[datetime] = field(
        converter=lambda v: optional_datetime(v), default=None)
    finished: Optional[datetime] = field(
        converter=lambda v: optional_datetime(v), default=None)
    definition: str
    project_id: str


class WorkflowsEndpoint:
    """Metafold workflows endpoint."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def list(
        self,
        sort: Optional[str] = None,
        q: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> list[Workflow]:
        """List jobs.

        Args:
            sort: Sort string. For details on syntax see the Metafold API docs.
                Supported sorting fields are: "id", "created", "started", or "finished".
            q: Query string. For details on syntax see the Metafold API docs.
                Supported search fields are: "id" and "state".
            project_id: Workflow project ID.

        Returns:
            List of job resources.
        """
        project_id = self._client.project_id(project_id)
        url = f"/projects/{project_id}/workflows"
        payload = asdict(sort=sort, q=q)
        r: Response = self._client.get(url, params=payload)
        return [Workflow(**w) for w in r.json()]

    def get(self, workflow_id: str, project_id: Optional[str] = None) -> Workflow:
        """Get a workflow.

        Args:
            workflow_id: ID of workflow to get.
            project_id: Workflow project ID.

        Returns:
            Workflow resource.
        """
        project_id = self._client.project_id(project_id)
        url = f"/projects/{project_id}/workflows/{workflow_id}"
        r: Response = self._client.get(url)
        return Workflow(**r.json())

    def run(
        self, definition: str,
        parameters: Optional[dict[str, str]] = None,
        assets: Optional[dict[str, str]] = None,
        timeout: Union[int, float] = 120,
        project_id: Optional[str] = None,
    ) -> Workflow:
        """Dispatch a new workflow and wait for it to complete.

        Workflow completion does not indicate success. Access the completed workflow's
        state to check for success/failure.

        Args:
            definition: Workflow definition YAML.
            parameters: Parameter mapping for jobs in the definition.
            assets: Asset mapping for jobs in the definition.
            timeout: Time in seconds to wait for a result.
            project_id: Workflow project ID.

        Returns:
            Completed workflow resource.
        """
        project_id = self._client.project_id(project_id)
        payload = asdict(definition=definition, parameters=parameters, assets=assets)
        r: Response = self._client.post(f"/projects/{project_id}/workflows", json=payload)
        url = r.json()["link"]
        try:
            r = self._client.poll(url, timeout)
        except PollTimeout as e:
            raise RuntimeError(
                f"Workflow failed to complete within {timeout} seconds"
            ) from e
        return Workflow(**r.json())

    def cancel(self, workflow_id: str, project_id: Optional[str] = None) -> Workflow:
        """Cancel a running workflow.

        Args:
            workflow_id: ID of workflow to cancel.
            project_id: Workflow project ID.

        Returns:
            Workflow resource.
        """
        project_id = self._client.project_id(project_id)
        url = f"/projects/{project_id}/workflows/{workflow_id}/cancel"
        r: Response = self._client.post(url)
        return Workflow(**r.json())

    def delete(self, workflow_id: str, project_id: Optional[str] = None):
        """Delete a workflow.

        Args:
            workflow_id: ID of workflow to delete.
            project_id: Workflow project ID.
        """
        project_id = self._client.project_id(project_id)
        url = f"/projects/{project_id}/workflows/{workflow_id}"
        self._client.delete(url)
