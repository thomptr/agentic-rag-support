"""Gateway-routed executor: invokes tools via AgentCore Tool Gateway over MCP.

Replaces the in-process `src.tools.orchestrator` for action tools (FR-014 hard
cutover). Approval, audit, and guardrails remain in-process and are expected
to run BEFORE this module is called.

Flow:
1. Open a Langfuse parent span for the tool call.
2. Build the MCP payload with the tool name, parameters, and trace_meta.
3. Get a JWT from the in-memory cache.
4. POST to the Gateway. On 401, invalidate the cache, refresh, retry once.
5. Wrap the Gateway response into the existing ToolResult shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.api.cognito_jwt_cache import JWTCache, TokenFetchError
from src.config import settings
from src.tools.audit import log_tool_attempt, log_tool_failed, log_tool_success


@dataclass
class ToolResult:
    tool_name: str
    status: str  # "success" | "failed" | "blocked"
    result: dict | None
    error: str | None


class GatewayHTTPError(RuntimeError):
    """Raised when the Gateway returns a non-2xx HTTP status."""

    def __init__(self, *, status_code: int, message: str) -> None:
        super().__init__(f"{status_code}: {message}")
        self.status_code = status_code
        self.message = message


# Module-level cache and MCP transport. Patched in tests; constructed lazily in
# production so import doesn't fail when Cognito settings are absent (local dev).
_jwt_cache: JWTCache | None = None


def _get_cache() -> JWTCache:
    global _jwt_cache
    if _jwt_cache is None:
        _jwt_cache = JWTCache(
            token_url=settings.cognito_token_url,
            client_id=settings.cognito_client_id,
            client_secret=settings.cognito_client_secret,
            scope=settings.cognito_scope,
        )
    return _jwt_cache


def _mcp_call(*, gateway_url: str, jwt: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST the tool-call payload to the Gateway. Returns the response body.

    Raises GatewayHTTPError on non-2xx status. Real implementation uses the
    `mcp` Python client; this stub structure exists so tests can patch in
    deterministic responses without an MCP dependency.
    """
    import json
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        f"{gateway_url}/invocations",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace") if exc.fp else ""
        raise GatewayHTTPError(status_code=exc.code, message=body or exc.reason) from exc


def invoke(
    tool_name: str,
    parameters: dict,
    session_id: str,
    agent_type: str,
    trace_meta: dict,
) -> ToolResult:
    """Invoke a Gateway-fronted tool. Returns the existing ToolResult shape so
    the LangGraph dispatch node doesn't need to change its consumer logic.

    `trace_meta` is propagated to the Lambda in the payload; the agent's
    parent span is opened by the caller (the LangGraph node) so this function
    doesn't open one itself — that keeps the span boundary in the graph.
    """
    log_tool_attempt(tool_name, parameters, "remote", session_id)
    cache = _get_cache()

    payload = {
        "tool_name": tool_name,
        "parameters": parameters,
        "trace_meta": trace_meta,
    }

    # Two attempts: original + one refresh-and-retry on 401.
    for attempt in (1, 2):
        try:
            jwt = cache.get()
        except TokenFetchError as exc:
            return _fail(tool_name, parameters, session_id, f"jwt_fetch_failed: {exc}")

        try:
            response = _mcp_call(gateway_url=settings.gateway_url, jwt=jwt, payload=payload)
        except GatewayHTTPError as exc:
            if exc.status_code == 401 and attempt == 1:
                cache.invalidate()
                continue
            return _fail(
                tool_name,
                parameters,
                session_id,
                f"gateway_{exc.status_code}: {exc.message}",
            )

        # Lambda returned an envelope per contracts/tool-lambda.md
        if response.get("status") == "success":
            log_tool_success(
                tool_name=tool_name,
                parameters=parameters,
                result=response.get("result", {}),
                duration_ms=0.0,
                session_id=session_id,
            )
            return ToolResult(
                tool_name=tool_name, status="success", result=response.get("result"), error=None
            )

        # status == "error"
        return _fail(
            tool_name,
            parameters,
            session_id,
            f"{response.get('error_code', 'unknown_error')}: {response.get('error_message', '')}",
        )

    # Unreachable in practice — the loop returns on every path.
    return _fail(tool_name, parameters, session_id, "exhausted_retries")


def _fail(tool_name: str, parameters: dict, session_id: str, message: str) -> ToolResult:
    log_tool_failed(
        tool_name=tool_name,
        parameters=parameters,
        error=message,
        session_id=session_id,
    )
    return ToolResult(tool_name=tool_name, status="failed", result=None, error=message)
