"""Gateway-routed executor: invokes tools via AgentCore Tool Gateway over MCP.

Replaces the in-process `src.tools.orchestrator` for action tools (FR-014 hard
cutover). Approval, audit, and guardrails remain in-process and are expected
to run BEFORE this module is called.

Protocol notes (learned the hard way):
- The Gateway URL ends in `/mcp` — POST the JSON-RPC body straight there,
  NOT to `{gateway_url}/invocations` (that returns "No Target found").
- The body is JSON-RPC 2.0 with `method="tools/call"`.
- Gateway-side MCP tool names are namespaced as `<target>___<tool>`, NOT the
  internal registry name. The mapping is hardcoded in `_AGENT_TO_MCP_TOOL`.
- `trace_meta` rides inside `params.arguments` (the Gateway passes the whole
  arguments dict through as the Lambda event payload — that's how the Lambda
  picks it up via `event["trace_meta"]`).
- Successful responses are wrapped: `result.content[0].text` is the JSON
  string that the Lambda actually returned (our `{status, result|error_code}`
  envelope). Unwrap it before treating the contents as the Lambda's result.

Flow:
1. Build the MCP payload with the mapped tool name, arguments, and trace_meta.
2. Get a JWT from the in-memory cache.
3. POST to the Gateway. On 401, invalidate the cache, refresh, retry once.
4. Unwrap the MCP envelope into the Lambda's `{status, result|error_*}` shape.
5. Wrap that into the existing ToolResult so callers don't change.
"""

from __future__ import annotations

import json
import uuid
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


# Per-tool routing: agent's internal tool name → (Gateway MCP tool name,
# Lambda's `tool_name` constant). The Lambda handler checks
# `event["tool_name"]` against its TOOL_NAME — so we must send the LAMBDA's
# internal name in the wrapped envelope, NOT the agent's name or the MCP name.
# Keep in sync with scripts/register-gateway-targets.sh + each Lambda's
# `TOOL_NAME = "..."` constant.
_TOOL_ROUTING: dict[str, tuple[str, str]] = {
    # agent_tool_name: (mcp_tool_name, lambda_tool_name)
    "create_support_ticket": ("create-ticket___create_ticket", "create_ticket"),
    "issue_refund": ("issue-refund___issue_refund", "issue_refund"),
    "order_status_lookup": ("order-status___order_status", "order_status"),
}


# Module-level cache. Patched in tests; constructed lazily in production so
# import doesn't fail when Cognito settings are absent (local dev).
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
    """POST the JSON-RPC body to the Gateway. Returns the parsed JSON response.

    Raises GatewayHTTPError on non-2xx status. Real implementation uses urllib;
    the boundary exists so tests can patch in deterministic responses without
    standing up an MCP transport.
    """
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        gateway_url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace") if exc.fp else ""
        raise GatewayHTTPError(status_code=exc.code, message=body or exc.reason) from exc


def _unwrap_mcp_response(rpc_response: dict[str, Any]) -> dict[str, Any]:
    """Pull the Lambda's `{status, result|error_*}` envelope out of an MCP
    `tools/call` response. Returns a synthesized error envelope if the
    response shape is unexpected so callers can render a clean failure."""
    if "error" in rpc_response:
        err = rpc_response["error"]
        return {
            "status": "error",
            "error_code": f"rpc_{err.get('code', 'unknown')}",
            "error_message": err.get("message", str(err)),
        }

    result = rpc_response.get("result") or {}
    if result.get("isError"):
        # MCP-level error (e.g. Gateway couldn't route to the Lambda). Surface
        # the first content item if present.
        content = result.get("content") or [{}]
        text = content[0].get("text") if isinstance(content[0], dict) else str(content[0])
        return {"status": "error", "error_code": "mcp_error", "error_message": text or ""}

    content = result.get("content") or []
    if not content or not isinstance(content[0], dict):
        return {
            "status": "error",
            "error_code": "empty_mcp_response",
            "error_message": "Gateway returned no content",
        }

    text = content[0].get("text", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Lambda emitted a non-JSON body — treat as opaque success text.
        return {"status": "success", "result": {"text": text}}


def invoke(
    tool_name: str,
    parameters: dict,
    session_id: str,
    agent_type: str,
    trace_meta: dict,
) -> ToolResult:
    """Invoke a Gateway-fronted tool. Returns the existing ToolResult shape so
    the LangGraph dispatch node doesn't need to change its consumer logic.

    `trace_meta` is propagated to the Lambda by embedding it in the MCP
    `arguments` payload; the Gateway passes arguments through verbatim as the
    Lambda event.
    """
    log_tool_attempt(tool_name, parameters, "remote", session_id)
    cache = _get_cache()

    routing = _TOOL_ROUTING.get(tool_name)
    if routing is None:
        return _fail(
            tool_name,
            parameters,
            session_id,
            f"unknown_gateway_tool: no Gateway mapping for {tool_name!r}",
        )
    mcp_tool_name, lambda_tool_name = routing

    # The Gateway passes `arguments` through verbatim as the Lambda event, so
    # we must wrap parameters + trace_meta into the envelope shape the Lambda
    # handlers expect: {tool_name, parameters, trace_meta}. (The Gateway's
    # advertised inputSchema looks like raw params, but it doesn't actually
    # validate against it for Lambda targets — pass-through is the truth.)
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {
            "name": mcp_tool_name,
            "arguments": {
                "tool_name": lambda_tool_name,
                "parameters": parameters,
                "trace_meta": trace_meta,
            },
        },
    }

    # Two attempts: original + one refresh-and-retry on 401.
    for attempt in (1, 2):
        try:
            jwt = cache.get()
        except TokenFetchError as exc:
            return _fail(tool_name, parameters, session_id, f"jwt_fetch_failed: {exc}")

        try:
            rpc_response = _mcp_call(gateway_url=settings.gateway_url, jwt=jwt, payload=payload)
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

        envelope = _unwrap_mcp_response(rpc_response)
        if envelope.get("status") == "success":
            log_tool_success(
                tool_name=tool_name,
                parameters=parameters,
                result=envelope.get("result", {}),
                duration_ms=0.0,
                session_id=session_id,
            )
            return ToolResult(
                tool_name=tool_name,
                status="success",
                result=envelope.get("result"),
                error=None,
            )

        return _fail(
            tool_name,
            parameters,
            session_id,
            f"{envelope.get('error_code', 'unknown_error')}: {envelope.get('error_message', '')}",
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
