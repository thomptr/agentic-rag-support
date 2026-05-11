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


def _success_response(trace_id: str) -> dict:
    return {
        "status": "success",
        "result": {"ticket_id": "TKT-1"},
        "trace_id": trace_id,
    }


class TestGatewayExecutor:
    @patch("src.tools.gateway_executor._jwt_cache")
    @patch("src.tools.gateway_executor._mcp_call")
    def test_jwt_cache_miss_triggers_fetch(self, mock_mcp, mock_cache):
        meta = _trace_meta()
        mock_cache.get.return_value = "jwt-fresh"
        mock_mcp.return_value = _success_response(meta["trace_id"])

        result = invoke(
            "create_ticket", {"subject": "s", "description": "d"}, "session-1", "billing", meta
        )

        assert isinstance(result, ToolResult)
        assert result.status == "success"
        mock_cache.get.assert_called_once()

    @patch("src.tools.gateway_executor._jwt_cache")
    @patch("src.tools.gateway_executor._mcp_call")
    def test_jwt_cache_hit_reuses_token(self, mock_mcp, mock_cache):
        meta = _trace_meta()
        mock_cache.get.return_value = "jwt-fresh"
        mock_mcp.return_value = _success_response(meta["trace_id"])

        invoke("create_ticket", {}, "s", "a", meta)
        invoke("create_ticket", {}, "s", "a", meta)
        invoke("create_ticket", {}, "s", "a", meta)

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
            _success_response(meta["trace_id"]),
        ]

        result = invoke("create_ticket", {}, "s", "a", meta)

        assert result.status == "success"
        mock_cache.invalidate.assert_called_once()
        assert mock_mcp.call_count == 2

    @patch("src.tools.gateway_executor._jwt_cache")
    @patch("src.tools.gateway_executor._mcp_call")
    def test_gateway_504_fails_without_retry(self, mock_mcp, mock_cache):
        meta = _trace_meta()
        mock_cache.get.return_value = "fresh-jwt"
        mock_mcp.side_effect = GatewayHTTPError(status_code=504, message="Gateway Timeout")

        result = invoke("create_ticket", {}, "s", "a", meta)

        assert result.status == "failed"
        assert mock_mcp.call_count == 1

    @patch("src.tools.gateway_executor._jwt_cache")
    @patch("src.tools.gateway_executor._mcp_call")
    def test_trace_meta_propagated_in_every_request(self, mock_mcp, mock_cache):
        meta = _trace_meta()
        mock_cache.get.return_value = "jwt"
        mock_mcp.return_value = _success_response(meta["trace_id"])

        invoke("create_ticket", {"subject": "s", "description": "d"}, "session-1", "billing", meta)

        # The MCP call argument should be the full payload including trace_meta.
        _, kwargs = mock_mcp.call_args
        payload = kwargs.get("payload") or mock_mcp.call_args.args[-1]
        assert isinstance(payload, dict)
        assert payload["trace_meta"]["trace_id"] == meta["trace_id"]
        assert payload["trace_meta"]["parent_span_id"] == meta["parent_span_id"]
