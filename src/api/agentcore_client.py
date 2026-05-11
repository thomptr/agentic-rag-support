"""HTTP client for invoking the AgentCore Runtime endpoint.

Uses AWS SigV4 request signing via botocore.  Implements retry logic for
transient errors (429, 500, 503) with exponential back-off.
"""

import json
import time
import uuid
from typing import Any

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

from src.config import settings


class AgentCoreClient:
    """Invoke AgentCore Runtime with SigV4-signed HTTP requests."""

    _MAX_RETRIES = 3
    _RETRY_STATUS = {429, 500, 503}
    _INITIAL_BACKOFF = 1.0  # seconds

    def __init__(self) -> None:
        session = boto3.Session(region_name=settings.aws_region)
        self._credentials: Credentials = session.get_credentials().get_frozen_credentials()
        self._region = settings.aws_region
        self._endpoint = settings.agentcore_endpoint_url.rstrip("/")
        self._runtime_arn = settings.agentcore_runtime_arn

    def invoke(
        self,
        prompt: str,
        session_id: str | None = None,
        *,
        model_override: str | None = None,
        guardrails_enabled: bool = True,
    ) -> dict[str, Any]:
        sid = session_id or str(uuid.uuid4())
        payload = {
            "prompt": prompt,
            "session_id": sid,
            "query_id": str(uuid.uuid4()),
            "run_id": str(uuid.uuid4()),
            "model_override": model_override,
            "guardrails_enabled": guardrails_enabled,
        }

        url = f"{self._endpoint}/invocations?qualifier=DEFAULT"
        body = json.dumps(payload).encode()

        for attempt in range(self._MAX_RETRIES):
            response = self._signed_post(url, body)
            if response.status_code == 200:
                return response.json()
            if response.status_code not in self._RETRY_STATUS:
                response.raise_for_status()
            if attempt < self._MAX_RETRIES - 1:
                time.sleep(self._INITIAL_BACKOFF * (2**attempt))

        response.raise_for_status()
        return {}  # unreachable

    def _signed_post(self, url: str, body: bytes) -> requests.Response:
        aws_request = AWSRequest(
            method="POST",
            url=url,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        SigV4Auth(self._credentials, "bedrock-agentcore", self._region).add_auth(aws_request)
        prepared = requests.Request(
            method="POST",
            url=url,
            headers=dict(aws_request.headers),
            data=body,
        ).prepare()
        with requests.Session() as s:
            return s.send(prepared, timeout=60)


_client: AgentCoreClient | None = None


def get_client() -> AgentCoreClient:
    global _client
    if _client is None:
        _client = AgentCoreClient()
    return _client
