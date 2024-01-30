from metafold.client import Client
from metafold.assets import AssetsEndpoint
from metafold.jobs import JobsEndpoint


class MetafoldClient(Client):
    """Metafold REST API client.

    Attributes:
        assets: Sub-client for assets endpoint.
        jobs: Sub-client for jobs endpoint.
    """

    def __init__(
        self, access_token: str, project_id: str,
        base_url: str = "https://api.metafold3d.com",
    ) -> None:
        """Initialize Metafold API client.

        Args:
            access_token: Metafold API secret key.
            project_id: ID of the project to make API calls against.
            base_url: Metafold API URL. Used for internal testing.
        """
        super().__init__(access_token, project_id, base_url=base_url)
        self.assets = AssetsEndpoint(self)
        self.jobs = JobsEndpoint(self)
