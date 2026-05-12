"""SC-005: tool failure surfaces in Langfuse with the full parent→child chain.

Gated on RUN_INTEGRATION=1 because it depends on the live AgentCore Runtime,
a live Langfuse project, and the `issue_refund` Lambda being temporarily
toggled into chaos mode (`FAIL_MODE=business_rule_violation`).

The runbook in `docs/runbooks/diagnose-tool-failure.md` describes how to
enable chaos mode + revert it; this test reads `LAMBDA_NAME` and the chaos-mode
toggle from env so a CI runner can drive the whole flow without code changes.
"""

from __future__ import annotations

import os
import subprocess
import time
import uuid

import pytest
import requests

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1",
    reason="Set RUN_INTEGRATION=1 to run trace-continuity check against deployed dev.",
)


def _alb_dns() -> str:
    result = subprocess.run(
        ["tofu", "-chdir=infra/environments/dev", "output", "-raw", "alb_dns_name"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _toggle_chaos_mode(lambda_name: str, mode: str | None) -> None:
    """Set or unset FAIL_MODE on a deployed Lambda. mode=None clears it."""
    import boto3

    client = boto3.client("lambda", region_name="us-east-1")
    current = client.get_function_configuration(FunctionName=lambda_name)
    env = dict(current.get("Environment", {}).get("Variables", {}))
    if mode is None:
        env.pop("FAIL_MODE", None)
    else:
        env["FAIL_MODE"] = mode
    client.update_function_configuration(
        FunctionName=lambda_name,
        Environment={"Variables": env},
    )
    # Wait for config update to settle.
    for _ in range(20):
        cfg = client.get_function_configuration(FunctionName=lambda_name)
        if cfg.get("LastUpdateStatus") == "Successful":
            return
        time.sleep(2)


def test_tool_failure_shows_in_langfuse_with_full_chain():
    """Force issue_refund to fail, then assert the trace shows the error end-to-end.

    Steps:
    1. Set FAIL_MODE=business_rule_violation on the deployed issue_refund Lambda.
    2. Send a /query that's likely to trigger issue_refund.
    3. Expect 200 with a tool-failure summary in the response.
    4. Query Langfuse for the session's trace and verify the child span carries
       error_code=business_rule_violation in its metadata.
    5. Clear FAIL_MODE.
    """
    lambda_name = os.environ.get("LAMBDA_NAME", "dev-agentic-rag-issue_refund")
    alb = _alb_dns()
    session_id = f"obs-continuity-{uuid.uuid4()}"

    _toggle_chaos_mode(lambda_name, "business_rule_violation")
    try:
        resp = requests.post(
            f"http://{alb}/query",
            json={
                "query_text": "Please refund order ORD-12345 — $49.99 — the item was defective.",
                "session_id": session_id,
            },
            timeout=60,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        # The agent should surface the tool error in some form, not 500.
        assert body.get("response_text"), "agent returned no response_text on tool failure"

        # If the agent exposes a langfuse_trace_id (T124), use it to query Langfuse.
        # Otherwise the manual diagnosis runbook is the source of truth.
        trace_id = body.get("langfuse_trace_id")
        if not trace_id:
            pytest.skip(
                "agent does not yet surface langfuse_trace_id (T124); manual check via runbook"
            )

        from langfuse import Langfuse  # lazy import

        lf = Langfuse()
        # Poll because Langfuse ingest is eventually-consistent.
        observation = None
        deadline = time.time() + 30
        while time.time() < deadline:
            trace = lf.fetch_trace(trace_id)
            obs = (trace and trace.data and trace.data.get("observations")) or []
            for o in obs:
                if (o.get("metadata") or {}).get("error_code") == "business_rule_violation":
                    observation = o
                    break
            if observation:
                break
            time.sleep(2)
        assert observation is not None, (
            f"no observation with error_code=business_rule_violation found in trace {trace_id}"
        )
    finally:
        _toggle_chaos_mode(lambda_name, None)
