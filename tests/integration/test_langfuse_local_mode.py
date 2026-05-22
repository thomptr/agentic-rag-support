"""Regression: local-mode FastAPI must open a Langfuse parent trace.

This locks the fix for the "Streamlit produces no Langfuse traces" bug. Two
failure modes were possible historically:

  1. `_init_langfuse()` only accepted Secrets-Manager ARNs (LANGFUSE_*_REF),
     so a `.env` with raw LANGFUSE_SECRET_KEY/LANGFUSE_PUBLIC_KEY left the
     client uninitialized.
  2. The local-mode `/query` handler called `graph.invoke()` directly without
     wrapping it in `langfuse_init.trace(...)`. Every child `span()` /
     `generation()` call then saw `_current_parent is None` and no-oped,
     so even a correctly initialized client emitted nothing for local traffic.

If either regresses, the assertions below break — keeping the bug from
silently coming back.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def _mock_graph_result() -> dict:
    return {
        "response_text": "ok",
        "classified_domain": "billing",
        "classified_domains": ["billing"],
        "confidence_rationale": "test",
        "current_node": "response_generator",
        "citations": [],
        "raw_retrieval_results": [],
        "merged_results": [],
        "retrieved_documents": [],
        "retrieval_confidence": {"score": 0.9},
        "retrieval_attempt": 1,
        "max_retrieval_attempts": 3,
        "log_events": [],
    }


def test_init_accepts_raw_env_keys(monkeypatch):
    """Setting LANGFUSE_SECRET_KEY/LANGFUSE_PUBLIC_KEY (no ARNs) must initialize.

    Calls `_init_langfuse()` directly with a patched SDK so the module-level
    `_LANGFUSE` global isn't mutated for downstream tests.
    """
    monkeypatch.delenv("LANGFUSE_SECRET_REF", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_REF", raising=False)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://example.langfuse.com")

    fake_client = MagicMock(name="LangfuseClient")
    with patch("src.observability.langfuse_init.Langfuse", return_value=fake_client):
        from src.observability import langfuse_init

        client = langfuse_init._init_langfuse()
        assert client is fake_client
        assert langfuse_init.init_status["state"] == "ok"
        assert langfuse_init.init_status["source"] == "env"
        assert langfuse_init.init_status["host"] == "https://example.langfuse.com"


def test_init_failure_is_loud_when_required(monkeypatch):
    """LANGFUSE_REQUIRED=true must turn a missing-creds skip into a hard error.

    This is the escape hatch for CI / production: opt in to fail-fast so a
    misconfig surfaces on boot instead of silently dropping every trace.
    """
    monkeypatch.delenv("LANGFUSE_SECRET_REF", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_REF", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.setenv("LANGFUSE_REQUIRED", "true")

    from src.observability import langfuse_init

    with pytest.raises(RuntimeError, match="LANGFUSE_REQUIRED"):
        langfuse_init._init_langfuse()


def test_health_endpoint_exposes_langfuse_status():
    """/health must surface the init state so the UI can show a badge."""
    from src.api.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "langfuse" in data, "health response must include langfuse status block"
    assert data["langfuse"]["state"] in {"ok", "disabled", "failed"}


@patch("src.graph.workflow.graph")
def test_local_query_opens_langfuse_parent_trace(mock_graph, monkeypatch):
    """The local-mode /query handler must wrap graph.invoke in langfuse.trace(...).

    Without this, every span()/generation() inside the graph nodes sees
    `_current_parent is None` and emits nothing — which is exactly the
    silent-failure mode we hit before.
    """
    mock_graph.invoke.return_value = _mock_graph_result()

    fake_trace_handle = MagicMock()
    fake_trace_handle.id = "trace-xyz-789"

    # Patch the trace() context manager so we can assert it was entered AND
    # observe the trace_id propagating into the response.
    from contextlib import contextmanager

    entered = {"count": 0}

    @contextmanager
    def fake_trace(*, name, input_payload=None, metadata=None, session_id=None, user_id=None):
        entered["count"] += 1
        entered["name"] = name
        entered["session_id"] = session_id
        yield fake_trace_handle

    monkeypatch.setattr("src.observability.langfuse_init.trace", fake_trace)

    from src.api.main import app

    client = TestClient(app)
    response = client.post("/query", json={"query_text": "test", "session_id": "sess-1"})

    assert response.status_code == 200
    assert entered["count"] == 1, (
        "local-mode /query did not open a Langfuse parent trace — "
        "graph.invoke must run inside `with langfuse_init.trace(...)`"
    )
    assert entered["name"] == "agent.invoke"
    assert entered["session_id"] == "sess-1"

    data = response.json()
    assert data["langfuse_trace_id"] == "trace-xyz-789", (
        "local-mode /query must surface the Langfuse trace id back to the caller "
        "so the Streamlit UI can link to it"
    )
    fake_trace_handle.update.assert_called_once()
