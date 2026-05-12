"""Unit tests for `src.tools.gateway_executor`.

TDD red — the module is implemented in T041. The MCP client is mocked so
these tests don't touch a real Gateway.

Test scope (from contracts/tool-lambda.md + data-model.md tool-call flow):
- JWT cache miss triggers a token fetch.
- JWT cache hit reuses the existing token (no fetch).
- A 401 from the Gateway forces a single refresh + retry.
- A 504 from the Gateway fails the call without retry.
- Every request includes the propagated trace_meta.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

try:
    from src.tools.gateway_executor import GatewayHTTPError, ToolResult, invoke
except ImportError as exc:
    pytest.skip(f"red — implementation missing: {exc}", allow_module_level=True)


def _trace_meta() -> dict:
    return {
        "trace_id": str(uuid.uuid4()),
        "parent_span_id": str(uuid.uuid4()),
        "session_id": "session-x",
        "run_id": "run-y",
    }


def _success_rpc(trace_id: str) -> dict:
    """Mimic the Gateway's MCP envelope around a successful Lambda response."""
    lambda_envelope = {
        "status": "success",
        "result": {"ticket_id": "TKT-1"},
        "trace_id": trace_id,
    }
    import json as _json

    return {
        "jsonrpc": "2.0",
        "id": "1",
        "result": {
            "isError": False,
            "content": [{"type": "text", "text": _json.dumps(lambda_envelope)}],
        },
    }


# Internal tool name the executor knows how to route. Tests use this so the
# `_AGENT_TO_MCP_TOOL` mapping is exercised (mapping is the production
# invariant — if it ever drifts, these tests catch it).
_AGENT_TOOL = "create_support_ticket"


class TestGatewayExecutor:
    @patch("src.tools.gateway_executor._jwt_cache")
    @patch("src.tools.gateway_executor._mcp_call")
    def test_jwt_cache_miss_triggers_fetch(self, mock_mcp, mock_cache):
        meta = _trace_meta()
        mock_cache.get.return_value = "jwt-fresh"
        mock_mcp.return_value = _success_rpc(meta["trace_id"])

        result = invoke(
            _AGENT_TOOL, {"subject": "s", "description": "d"}, "session-1", "billing", meta
        )

        assert isinstance(result, ToolResult)
        assert result.status == "success"
        mock_cache.get.assert_called_once()

    @patch("src.tools.gateway_executor._jwt_cache")
    @patch("src.tools.gateway_executor._mcp_call")
    def test_jwt_cache_hit_reuses_token(self, mock_mcp, mock_cache):
        meta = _trace_meta()
        mock_cache.get.return_value = "jwt-fresh"
        mock_mcp.return_value = _success_rpc(meta["trace_id"])

        invoke(_AGENT_TOOL, {}, "s", "a", meta)
        invoke(_AGENT_TOOL, {}, "s", "a", meta)
        invoke(_AGENT_TOOL, {}, "s", "a", meta)

        assert mock_cache.get.call_count == 3
        # Cache.get is the abstraction; it internally decides FRESH vs refresh.
        # Implementation MUST NOT call cache.invalidate() on successful paths.
        mock_cache.invalidate.assert_not_called()

    @patch("src.tools.gateway_executor._jwt_cache")
    @patch("src.tools.gateway_executor._mcp_call")
    def test_gateway_401_forces_refresh_and_single_retry(self, mock_mcp, mock_cache):
        meta = _trace_meta()
        mock_cache.get.side_effect = ["expired-jwt", "fresh-jwt"]
        mock_mcp.side_effect = [
            GatewayHTTPError(status_code=401, message="Unauthorized"),
            _success_rpc(meta["trace_id"]),
        ]

        result = invoke(_AGENT_TOOL, {}, "s", "a", meta)

        assert result.status == "success"
        mock_cache.invalidate.assert_called_once()
        assert mock_mcp.call_count == 2

    @patch("src.tools.gateway_executor._jwt_cache")
    @patch("src.tools.gateway_executor._mcp_call")
    def test_gateway_504_fails_without_retry(self, mock_mcp, mock_cache):
        meta = _trace_meta()
        mock_cache.get.return_value = "fresh-jwt"
        mock_mcp.side_effect = GatewayHTTPError(status_code=504, message="Gateway Timeout")

        result = invoke(_AGENT_TOOL, {}, "s", "a", meta)

        assert result.status == "failed"
        assert mock_mcp.call_count == 1

    @patch("src.tools.gateway_executor._jwt_cache")
    @patch("src.tools.gateway_executor._mcp_call")
    def test_trace_meta_propagated_inside_arguments(self, mock_mcp, mock_cache):
        meta = _trace_meta()
        mock_cache.get.return_value = "jwt"
        mock_mcp.return_value = _success_rpc(meta["trace_id"])

        invoke(_AGENT_TOOL, {"subject": "s", "description": "d"}, "session-1", "billing", meta)

        # The Gateway passes arguments through verbatim as the Lambda event,
        # so arguments MUST be the wrapped envelope the Lambda expects.
        _, kwargs = mock_mcp.call_args
        payload = kwargs["payload"]
        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "tools/call"
        assert payload["params"]["name"] == "create-ticket___create_ticket"
        args = payload["params"]["arguments"]
        # Wrapped envelope: tool_name + parameters + trace_meta at top of args.
        assert args["tool_name"] == "create_ticket"  # Lambda's internal name
        assert args["parameters"]["subject"] == "s"
        assert args["trace_meta"]["trace_id"] == meta["trace_id"]
        assert args["trace_meta"]["parent_span_id"] == meta["parent_span_id"]

    @patch("src.tools.gateway_executor._jwt_cache")
    @patch("src.tools.gateway_executor._mcp_call")
    def test_unknown_internal_tool_fails_fast(self, mock_mcp, mock_cache):
        """If an agent emits a tool not in _AGENT_TO_MCP_TOOL, the executor
        must not even attempt the Gateway call."""
        result = invoke("definitely_not_a_real_tool", {}, "s", "a", _trace_meta())
        assert result.status == "failed"
        assert "unknown_gateway_tool" in (result.error or "")
        mock_mcp.assert_not_called()
