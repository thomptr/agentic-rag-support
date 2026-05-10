"""Unit tests for the frontend API client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest


class TestSendQuery:
    def test_send_query_returns_response_dict(self):
        from src.frontend.api_client import send_query

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "query_id": "q-123",
            "response_text": "Here is the answer.",
            "agent": "billing_agent",
            "routing_rationale": "billing domain",
            "citations": [],
            "metadata": {
                "run_id": "r-1",
                "total_latency_ms": 500.0,
                "llm_calls": 1,
                "retrieval_calls": 1,
                "documents_retrieved": 3,
                "retrieval_confidence": 0.85,
                "classified_domains": ["billing"],
                "classified_domain": "billing",
                "retrieval_attempts": 1,
                "documents_after_dedup": 3,
            },
            "tool_calls": [],
            "action_taken": False,
            "pending_approvals": [],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.frontend.api_client._client") as mock_client:
            mock_client.post.return_value = mock_response
            result = send_query("How do I update billing?", session_id="s-1")

        assert result["query_id"] == "q-123"
        assert result["response_text"] == "Here is the answer."

    def test_send_query_passes_guardrails_enabled(self):
        from src.frontend.api_client import send_query

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "query_id": "q-1",
            "response_text": "ok",
            "agent": "billing_agent",
            "routing_rationale": None,
            "citations": [],
            "tool_calls": [],
            "action_taken": False,
            "pending_approvals": [],
            "metadata": {
                "run_id": "r-1",
                "total_latency_ms": 100.0,
                "llm_calls": 1,
                "retrieval_calls": 0,
                "documents_retrieved": 0,
                "retrieval_confidence": None,
                "classified_domains": [],
                "classified_domain": None,
                "retrieval_attempts": 0,
                "documents_after_dedup": 0,
            },
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.frontend.api_client._client") as mock_client:
            mock_client.post.return_value = mock_response
            send_query("test", guardrails_enabled=False)
            call_kwargs = mock_client.post.call_args[1]
            assert call_kwargs["json"]["guardrails_enabled"] is False

    def test_send_query_passes_model_override(self):
        from src.frontend.api_client import send_query

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "query_id": "q-1",
            "response_text": "ok",
            "agent": "billing_agent",
            "routing_rationale": None,
            "citations": [],
            "tool_calls": [],
            "action_taken": False,
            "pending_approvals": [],
            "metadata": {
                "run_id": "r-1",
                "total_latency_ms": 100.0,
                "llm_calls": 1,
                "retrieval_calls": 0,
                "documents_retrieved": 0,
                "retrieval_confidence": None,
                "classified_domains": [],
                "classified_domain": None,
                "retrieval_attempts": 0,
                "documents_after_dedup": 0,
            },
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.frontend.api_client._client") as mock_client:
            mock_client.post.return_value = mock_response
            send_query("test", model_override="gpt-4o")
            call_kwargs = mock_client.post.call_args[1]
            assert call_kwargs["json"]["model_override"] == "gpt-4o"

    def test_send_query_raises_on_connect_error(self):
        from src.frontend.api_client import send_query

        with patch("src.frontend.api_client._client") as mock_client:
            mock_client.post.side_effect = httpx.ConnectError("connection refused")
            with pytest.raises(httpx.ConnectError):
                send_query("test")

    def test_send_query_raises_on_timeout(self):
        from src.frontend.api_client import send_query

        with patch("src.frontend.api_client._client") as mock_client:
            mock_client.post.side_effect = httpx.TimeoutException("timeout")
            with pytest.raises(httpx.TimeoutException):
                send_query("test")


class TestGetApprovals:
    def test_get_approvals_returns_list(self):
        from src.frontend.api_client import get_approvals

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"approvals": []}
        mock_response.raise_for_status = MagicMock()

        with patch("src.frontend.api_client._client") as mock_client:
            mock_client.get.return_value = mock_response
            result = get_approvals()

        assert result == []

    def test_get_approvals_returns_approval_items(self):
        from src.frontend.api_client import get_approvals

        approval = {
            "id": "a-1",
            "tool_name": "issue_refund",
            "parameters": {"amount": 50},
            "status": "pending",
            "created_at": "2026-01-01T00:00:00",
            "expires_at": "2026-01-01T05:00:00",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"approvals": [approval]}
        mock_response.raise_for_status = MagicMock()

        with patch("src.frontend.api_client._client") as mock_client:
            mock_client.get.return_value = mock_response
            result = get_approvals()

        assert len(result) == 1
        assert result[0]["tool_name"] == "issue_refund"


class TestApproveAction:
    def test_approve_action_calls_correct_endpoint(self):
        from src.frontend.api_client import approve_action

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "a-1",
            "status": "approved",
            "tool_name": "issue_refund",
            "result": None,
            "error": None,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.frontend.api_client._client") as mock_client:
            mock_client.post.return_value = mock_response
            result = approve_action("a-1")

        mock_client.post.assert_called_once()
        call_url = mock_client.post.call_args[0][0]
        assert "a-1" in call_url
        assert "approve" in call_url
        assert result["status"] == "approved"


class TestRejectAction:
    def test_reject_action_calls_correct_endpoint(self):
        from src.frontend.api_client import reject_action

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "a-1",
            "status": "rejected",
            "reason": "user rejected",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("src.frontend.api_client._client") as mock_client:
            mock_client.post.return_value = mock_response
            result = reject_action("a-1")

        call_url = mock_client.post.call_args[0][0]
        assert "a-1" in call_url
        assert "reject" in call_url
        assert result["status"] == "rejected"


class TestHealthCheck:
    def test_health_check_returns_true_on_healthy(self):
        from src.frontend.api_client import health_check

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("src.frontend.api_client._client") as mock_client:
            mock_client.get.return_value = mock_response
            assert health_check() is True

    def test_health_check_returns_false_on_connect_error(self):
        from src.frontend.api_client import health_check

        with patch("src.frontend.api_client._client") as mock_client:
            mock_client.get.side_effect = httpx.ConnectError("refused")
            assert health_check() is False

    def test_health_check_returns_false_on_timeout(self):
        from src.frontend.api_client import health_check

        with patch("src.frontend.api_client._client") as mock_client:
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            assert health_check() is False
