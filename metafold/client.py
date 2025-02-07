from metafold.auth import AuthProvider
from metafold.exceptions import PollTimeout
from requests import HTTPError, Response, Session
from typing import Any, Callable, Optional, Union
from urllib.parse import urljoin
import platform
import time


class Client:
    """Base client."""

    def __init__(
        self,
        base_url: str,
        access_token: Optional[str] = None,
        project_id: Optional[str] = None,
        auth: Optional[AuthProvider] = None
    ) -> None:
        if bool(auth) == bool(access_token):
            raise ValueError(
                "Expected AuthProvider or access_token to be provided"
            )
        self._auth = auth
        self._default_project = project_id
        self._base_url = base_url
        self._session = Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": f"Python/{platform.python_version()}",
        })
        if access_token:
            self._session.headers.update({
                "Authorization": f"Bearer {access_token}",
            })

    def project_id(self, id: Optional[str] = None) -> str:
        id = id or self._default_project
        if not id:
            raise ValueError(
                "Project ID required, set a default ID when initializing the client"
            )
        return id

    def set_project_id(self, id: str) -> None:
        self._default_project = id

    def _request(
        self, request: Callable[..., Response], url: str,
        *args: Any, **kwargs: Any,
    ) -> Response:
        url = urljoin(self._base_url, url)
        headers = None
        if self._auth:
            headers = {"Authorization": f"Bearer {self._auth.get_token()}"}
        r: Response = request(url, *args, **kwargs, headers=headers)
        if not r.ok:
            body: dict[str, Any] = r.json()
            # Error responses aren't entirely consistent in the Metafold API,
            # for now we check for a handful of possible fields.
            reason = body.get("errors") or body.get("msg") or body.get("description")
            raise HTTPError(f"HTTP error occurred: {reason or r.reason}")
        return r

    def get(self, url: str, *args: Any, **kwargs: Any) ->  Response:
        return self._request(self._session.get, url, *args, **kwargs)

    def post(self, url: str, *args: Any, **kwargs: Any) ->  Response:
        return self._request(self._session.post, url, *args, **kwargs)

    def put(self, url: str, *args: Any, **kwargs: Any) ->  Response:
        return self._request(self._session.put, url, *args, **kwargs)

    def patch(self, url: str, *args: Any, **kwargs: Any) ->  Response:
        return self._request(self._session.patch, url, *args, **kwargs)

    def delete(self, url: str, *args: Any, **kwargs: Any) ->  Response:
        return self._request(self._session.delete, url, *args, **kwargs)

    def poll(
        self, url: str,
        timeout: Union[int, float] = 120,
        every: Union[int, float] = 1,
        ) -> Response:
        """Poll the given URL in regular intervals.

        Helpful for waiting on async processes given a status URL.

        Args:
            timeout: Time in seconds to wait for a result.
            every: Frequency in seconds.

        Returns:
            HTTP response.
        """
        t0 = time.monotonic()
        r = self.get(url)
        while r.status_code == 202:
            elapsed = time.monotonic() - t0
            if elapsed >= timeout:
                raise PollTimeout(f"Polling timed out: {url}")
            time.sleep(1)
            r = self.get(url)
        return r
