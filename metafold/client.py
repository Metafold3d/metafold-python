from requests import HTTPError, Response, Session
from typing import Any, Callable, Optional
from urllib.parse import urljoin
import platform


class Client:
    """Base client."""

    def __init__(
        self, access_token: str, base_url: str,
        project_id: Optional[str] = None,
    ) -> None:
        self._default_project = project_id
        self._base_url = base_url
        self._session = Session()
        self._session.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": f"Python/{platform.python_version()}",
        })

    def project_id(self, id: Optional[str] = None) -> str:
        id = id or self._default_project
        if not id:
            raise ValueError(
                "Project ID required, set a default ID when initializing the client"
            )
        return id

    def _request(
        self, request: Callable[..., Response], url: str,
        *args: Any, **kwargs: Any,
    ) -> Response:
        url = urljoin(self._base_url, url)
        r: Response = request(url, *args, **kwargs)
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
