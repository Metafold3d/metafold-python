from metafold.client import Client
from metafold.projects import ProjectsEndpoint
from metafold.assets import AssetsEndpoint
from metafold.jobs import JobsEndpoint
from metafold.workflows import WorkflowsEndpoint
from metafold.auth import AuthProvider
from typing import Optional


class MetafoldClient(Client):
    """Metafold REST API client.

    Attributes:
        projects: Sub-client for projects endpoint.
        assets: Sub-client for assets endpoint.
        jobs: Sub-client for jobs endpoint.
    """
    projects: ProjectsEndpoint
    assets: AssetsEndpoint
    jobs: JobsEndpoint
    workflows: WorkflowsEndpoint

    def __init__(
        self,
        access_token: Optional[str] = None,
        project_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        auth_domain: str = "metafold3d.us.auth0.com",
        base_url: str = "https://api.metafold3d.com/",
    ) -> None:
        """Initialize Metafold API client.

        Args:
            access_token: Metafold API secret key.
            project_id: ID of the project to make API calls against.
            base_url: Metafold API URL. Used for internal testing.
        """
        # client_id and client_secret have priority
        if not any([client_id and client_secret, access_token]):
            raise ValueError(
                "Expected client_id and client_secret or access_token to be provided"
            )
        elif client_id and client_secret:
            auth = AuthProvider(client_id, client_secret, auth_domain, base_url)
            super().__init__(base_url, auth=auth, project_id=project_id)
        else:
            super().__init__(base_url, access_token=access_token, project_id=project_id)

        self.projects = ProjectsEndpoint(self)
        self.assets = AssetsEndpoint(self)
        self.jobs = JobsEndpoint(self)
        self.workflows = WorkflowsEndpoint(self)
