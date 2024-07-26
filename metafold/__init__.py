from metafold.client import Client
from metafold.projects import ProjectsEndpoint
from metafold.assets import AssetsEndpoint
from metafold.jobs import JobsEndpoint
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

    def __init__(
        self, access_token: str,
        project_id: Optional[str] = None,
        base_url: str = "https://api.metafold3d.com",
    ) -> None:
        """Initialize Metafold API client.

        Args:
            access_token: Metafold API secret key.
            project_id: ID of the project to make API calls against.
            base_url: Metafold API URL. Used for internal testing.
        """
        super().__init__(access_token, base_url, project_id=project_id)
        self.projects = ProjectsEndpoint(self)
        self.assets = AssetsEndpoint(self)
        self.jobs = JobsEndpoint(self)
