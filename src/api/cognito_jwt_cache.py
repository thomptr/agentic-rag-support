"""In-memory M2M JWT cache for Cognito → AgentCore Gateway authentication.

State machine (data-model.md § State Transitions > JWT cache):
    EMPTY → (fetch) → FRESH → (exp - now < 60s) → STALE → (refresh) → FRESH

Single-process cache only — fine for the AgentCore Runtime container which
serves one user session at a time per container instance. Multi-instance
deployments still work because each container holds its own token.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.parse
import urllib.request

REFRESH_WINDOW_SECONDS = 60


class TokenFetchError(RuntimeError):
    """Raised when the Cognito token endpoint returns a non-success status."""


class JWTCache:
    def __init__(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str,
    ) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._access_token: str | None = None
        self._expires_at: float = 0.0  # absolute UNIX seconds

    def state(self) -> str:
        if self._access_token is None:
            return "EMPTY"
        if self._expires_at - time.time() < REFRESH_WINDOW_SECONDS:
            return "STALE"
        return "FRESH"

    def get(self) -> str:
        """Return a valid access token, refreshing if STALE/EMPTY.

        Raises TokenFetchError if the refresh attempt fails. Callers may catch
        the error and decide whether to retry; this class does not retry itself.
        """
        if self.state() != "FRESH":
            self._refresh()
        # State after refresh must be FRESH; defensive check.
        if self._access_token is None:
            raise TokenFetchError("token refresh produced no access_token")
        return self._access_token

    def invalidate(self) -> None:
        """Forget the cached token. Forces a refresh on the next get()."""
        self._access_token = None
        self._expires_at = 0.0

    def _refresh(self) -> None:
        token = self._request_token()
        access_token = token.get("access_token")
        expires_in = token.get("expires_in", 0)
        if not access_token or not isinstance(expires_in, (int, float)):
            raise TokenFetchError(f"malformed token response: {token!r}")
        self._access_token = access_token
        self._expires_at = time.time() + float(expires_in)

    def _request_token(self) -> dict:
        """POST to the Cognito token endpoint with HTTP Basic + form body.

        Cognito M2M client_credentials flow: the client_id/client_secret are
        sent as HTTP Basic auth, `grant_type=client_credentials` + `scope` go
        in the form body.
        """
        basic = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode()
        body = urllib.parse.urlencode(
            {"grant_type": "client_credentials", "scope": self._scope}
        ).encode()
        req = urllib.request.Request(
            self._token_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read())
        except Exception as exc:
            raise TokenFetchError(f"cognito token request failed: {exc!r}") from exc
        return payload
