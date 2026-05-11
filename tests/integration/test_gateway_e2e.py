"""End-to-end test of the agent → Gateway → Lambda path against a deployed dev env.

Skipped by default. Set RUN_INTEGRATION=1 to enable, plus credentials to call the
deployed ALB endpoint (no AWS creds needed for the HTTP path, but the Langfuse
verification step needs LANGFUSE_SECRET_KEY + LANGFUSE_PUBLIC_KEY locally).

What this verifies:
- POST /query → API → AgentCore → Gateway → Lambda chain works.
- The Langfuse trace for the session shows a parent span (agent tool dispatch)
  with at least one Lambda-side child span linked by the same trace_id.

TDD red — the supporting fixture functions reference modules that may not
exist yet (gateway_executor and the live deployment). Implementation lands
in T041 + T062 + T076.
"""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from typing import Any

import pytest
import requests

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1",
    reason="Set RUN_INTEGRATION=1 to run E2E against the deployed dev env.",
)


def _alb_dns() -> str:
    """Resolve ALB DNS via tofu output. Requires the dev workspace initialized."""
    result = subprocess.run(
        ["tofu", "-chdir=infra/environments/dev", "output", "-raw", "alb_dns_name"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _langfuse_trace_seen(trace_id: str, *, timeout_s: int = 30) -> dict[str, Any] | None:
    """Poll Langfuse for the trace_id; return the trace dict or None on timeout.

    Implementation note: the Langfuse Python SDK has a `fetch_trace()` helper; we
    use it lazily so this test file can collect even when the SDK isn't installed.
    """
    from langfuse import Langfuse  # local import keeps collection cheap

    client = Langfuse()
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        trace = client.fetch_trace(trace_id)
        if trace is not None and getattr(trace, "data", None):
            return trace.data
        time.sleep(2)
    return None


class TestGatewayE2E:
    def test_query_returns_tool_response_with_trace_continuity(self):
        """A /query that triggers create_ticket succeeds AND the Lambda's child span shows in Langfuse."""
        alb = _alb_dns()
        session_id = f"gateway-e2e-{uuid.uuid4()}"

        resp = requests.post(
            f"http://{alb}/query",
            json={
                "query_text": "Please open a support ticket for my double-charged bill.",
                "session_id": session_id,
            },
            timeout=60,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body.get("response_text"), "agent did not return a response"

        # The agent surface exposes a trace_id (added in T124 of US3 polish).
        # If T124 hasn't landed yet, this test still passes the HTTP shape check
        # and just skips the Langfuse continuity assertion.
        trace_id = body.get("langfuse_trace_id")
        if not trace_id:
            pytest.skip("agent does not yet surface langfuse_trace_id; integrate after T124")

        trace = _langfuse_trace_seen(trace_id)
        assert trace is not None, f"trace {trace_id} did not appear in Langfuse within timeout"
        observation_names = [o.get("name") for o in trace.get("observations", [])]
        assert any(n and n.startswith("tool.") for n in observation_names), (
            f"no Lambda-side child span found among observations: {observation_names}"
        )
