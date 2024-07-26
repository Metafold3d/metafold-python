from auth0.authentication import GetToken
from collections import namedtuple
from datetime import datetime, timedelta, timezone

Token = namedtuple("Token", ["access_token", "expires_at"])


class AuthProvider:
    def __init__(self, auth_domain: str, client_id: str, client_secret: str):
        self._auth_domain = auth_domain
        self._client_id = client_id

        self._get_token = GetToken(
            self._auth_domain,
            self._client_id,
            client_secret=client_secret,
        )
        self._token: Optional[Token] = None

    def get_token(self) -> str:
        now = datetime.now(timezone.utc)
        if not self._token or self._token.expires_at - now < timedelta(minutes=1):
            token = get_token.client_credentials(self._base_url)
            expires_at = now + timedelta(seconds=token["expires_in"])
            self._token = Token(token["access_token"], expires_at)
        return self._token.access_token
