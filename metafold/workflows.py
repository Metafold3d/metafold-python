from attrs import field, frozen
from datetime import datetime
from metafold.api import asdatetime, asdict, optional_datetime
from metafold.assets import Asset
from metafold.client import Client
from metafold.exceptions import PollTimeout
from metafold.jobs import Job
from requests import Response
from typing import Optional, Union, cast
import typing

if typing.TYPE_CHECKING:
    from metafold import MetafoldClient


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
    _client: "MetafoldClient"
    _jobs: dict[str, str] = field(factory=dict, init=False)

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

    def get_asset(self, path: str) -> Union[Asset, None]:
        """Retrieve an asset from the workflow by dot notation.

        Args:
            path: Path to asset in the form "job.name", e.g. "sample-mesh.volume"
                searches for the asset "volume" from the "sample-mesh" job.
        """
        job_name, asset_name = self._parse_path(path)
        job = self._find_job(job_name)
        if not job or not job.outputs.assets:
            return None
        for name, asset in job.outputs.assets.items():
            if name == asset_name:
                return asset
        return None

    def get_parameter(self, path: str) -> Union[str, None]:
        """Retrieve a parameter from the workflow by dot notation.

        Args:
            path: Path to parameter in the form "job.name", e.g. "sample-mesh.patch_size"
                searches for the parameter "patch_size" from the "sample-mesh" job.
        """
        job_name, param_name = self._parse_path(path)
        job = self._find_job(job_name)
        if not job or not job.outputs.params:
            return None
        for name, param in job.outputs.params.items():
            if name == param_name:
                return param
        return None

    def _find_job(self, name: str) -> Union[Job, None]:
        # FIXME(ryan): Update API to return job names as well as IDs.
        # For now we cache a mapping b/w job name and job id.
        if job_id := self._jobs.get(name):
            return self._client.jobs.get(job_id)

        for job_id in self.jobs:
            job = self._client.jobs.get(job_id)
            if job.name == name:
                self._jobs[name] = job_id
                return job
        return None

    @staticmethod
    def _parse_path(path: str) -> tuple[str, str]:
        first, second = path.split(".", maxsplit=1)
        return first, second


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
        return [Workflow(client=cast("MetafoldClient", self._client), **w) for w in r.json()]

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
        return Workflow(client=cast("MetafoldClient", self._client), **r.json())

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
        return Workflow(client=cast("MetafoldClient", self._client), **r.json())

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
        return Workflow(client=cast("MetafoldClient", self._client), **r.json())

    def delete(self, workflow_id: str, project_id: Optional[str] = None):
        """Delete a workflow.

        Args:
            workflow_id: ID of workflow to delete.
            project_id: Workflow project ID.
        """
        project_id = self._client.project_id(project_id)
        url = f"/projects/{project_id}/workflows/{workflow_id}"
        self._client.delete(url)
