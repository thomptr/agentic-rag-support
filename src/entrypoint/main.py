"""AgentCore Runtime entry point.

Wraps the LangGraph workflow graph with BedrockAgentCoreApp so it can be
deployed as an AgentCore Runtime container.  The container exposes:
  - POST /invocations  — agent invocation
  - GET  /ping         — health check

AgentCore Memory is used for persistent conversation history: each invocation
receives the last N turns from the session memory store and appends the new
exchange before returning.
"""

import json

import boto3
import structlog
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.runtime import BedrockAgentCoreApp

import src.observability.logger  # noqa: F401 — registers structlog + Langfuse processors
from src.config import settings
from src.graph.workflow import graph

# In VPC mode, outbound internet traffic (Langfuse cloud, OpenAI)
# routes through the NAT Gateway — no additional proxy config is required.
app = BedrockAgentCoreApp()
_memory = MemoryClient()
_log = structlog.get_logger()


def _resolve_secret_into_settings(arn: str, json_key: str, settings_attr: str) -> None:
    """Pull a Secrets Manager JSON value into a settings attribute at cold start.

    Both Cognito M2M client_secret and OpenAI API key follow the same shape:
    a SecretString of `{"<KEY>": "<value>"}`. Centralizing the fetch keeps the
    cold-start path consistent and makes failures easy to spot in CloudWatch.
    """
    if not arn:
        return
    try:
        client = boto3.client("secretsmanager", region_name=settings.aws_region)
        resp = client.get_secret_value(SecretId=arn)
        payload = json.loads(resp["SecretString"])
        setattr(settings, settings_attr, payload[json_key])
    except Exception as exc:  # noqa: BLE001 — surface in logs, don't crash boot
        _log.warning(
            "secret_fetch_failed",
            secret_arn=arn[:50] + "..." if len(arn) > 50 else arn,
            settings_attr=settings_attr,
            error=repr(exc),
        )


# Pull the credentials the deployed agent needs at runtime: OpenAI (classifier
# + downstream LLM calls) and Cognito (Gateway-tool JWTs).
_resolve_secret_into_settings(settings.openai_api_key_arn, "OPENAI_API_KEY", "openai_api_key")
_resolve_secret_into_settings(
    settings.cognito_client_secret_arn, "COGNITO_M2M_CLIENT_SECRET", "cognito_client_secret"
)


def _resolve_database_url() -> None:
    """Rewrite settings.database_url with the RDS master user creds.

    The infra wires `DATABASE_URL` as `postgresql+psycopg://user@host/db`
    (no password) and a separate `DB_MASTER_SECRET_ARN` env var pointing at
    the AWS-managed RDS master secret. We fetch username + password from that
    secret and reconstruct a full DSN so SQLAlchemy / psycopg can authenticate.
    """
    import os as _os

    arn = _os.environ.get("DB_MASTER_SECRET_ARN", "").strip()
    if not arn:
        return
    try:
        client = boto3.client("secretsmanager", region_name=settings.aws_region)
        resp = client.get_secret_value(SecretId=arn)
        creds = json.loads(resp["SecretString"])
        user = creds["username"]
        pw = creds["password"]
        host = _os.environ.get("DB_HOST", "").strip()
        dbname = _os.environ.get("DB_NAME", "agentic_rag").strip()
        if not host:
            _log.warning(
                "db_host_missing", note="DB_HOST env var unset; leaving DATABASE_URL untouched"
            )
            return
        settings.database_url = f"postgresql+psycopg://{user}:{pw}@{host}/{dbname}"
    except Exception as exc:  # noqa: BLE001 — surface but don't crash boot
        _log.warning("db_master_secret_fetch_failed", error=repr(exc))


_resolve_database_url()


@app.entrypoint
def agent_invocation(payload: dict, context) -> dict:
    import uuid as _uuid

    session_id: str = payload.get("session_id") or context.session_id
    # T124: generate one trace_id per invocation. This is the canonical
    # request-correlation key surfaced back through the API for log/Langfuse
    # lookups. Use the caller's run_id if provided (lets clients drive trace
    # IDs from outside); fall back to a fresh UUID otherwise.
    langfuse_trace_id = payload.get("run_id") or str(_uuid.uuid4())

    # Load conversation history from AgentCore Memory
    history = _load_history(session_id)

    initial_state = {
        "query_id": payload.get("query_id", session_id),
        "query_text": payload["prompt"],
        "messages": history,
        "classified_domain": None,
        "classified_domains": None,
        "confidence_rationale": None,
        "current_node": None,
        "retrieved_documents": None,
        "response_text": None,
        "citations": None,
        "run_id": langfuse_trace_id,
        "log_events": [],
        "search_queries": None,
        "raw_retrieval_results": None,
        "merged_results": None,
        "retrieval_confidence": None,
        "retrieval_attempt": 0,
        "max_retrieval_attempts": 3,
        "session_id": session_id,
        "tool_calls": None,
        "tool_results": None,
        "pending_approvals": None,
        "action_taken": None,
        "action_needed": None,
        "guardrails_enabled": payload.get("guardrails_enabled", True),
        "model_override": payload.get("model_override"),
    }

    result = graph.invoke(initial_state)
    response_text = result.get("response_text") or ""

    # Persist this exchange to AgentCore Memory
    _save_exchange(session_id, payload["prompt"], response_text)

    # Surface the metadata the API previously hardcoded to zeros. Local mode
    # computes the same fields in src/api/main.py — we mirror that work here
    # so cloud-mode `/query` callers see real classifier/llm/tool/retrieval
    # numbers instead of empty defaults.
    log_events = result.get("log_events") or []
    retrieval_confidence_obj = result.get("retrieval_confidence") or {}
    return {
        "result": response_text,
        "agent": result.get("current_node"),
        "citations": result.get("citations") or [],
        "session_id": session_id,
        "langfuse_trace_id": langfuse_trace_id,
        # Routing
        "classified_domain": result.get("classified_domain"),
        "classified_domains": result.get("classified_domains") or [],
        "confidence_rationale": result.get("confidence_rationale"),
        # Counts (derived from log_events stream)
        "llm_calls": sum(1 for e in log_events if e.get("event_type") == "llm_call"),
        "retrieval_calls": sum(1 for e in log_events if e.get("event_type") == "multi_retrieval"),
        # Retrieval
        "retrieval_attempts": result.get("retrieval_attempt", 0),
        "raw_retrieval_results": result.get("raw_retrieval_results") or [],
        "merged_results": result.get("merged_results") or [],
        "retrieval_confidence": retrieval_confidence_obj.get("score"),
        # Tool execution
        "tool_results": result.get("tool_results") or [],
        "action_taken": bool(result.get("action_taken")),
        "pending_approvals": result.get("pending_approvals") or [],
    }


def _load_history(session_id: str) -> list[dict]:
    try:
        turns = _memory.get_session_history(session_id=session_id, max_turns=10)
        messages = []
        for turn in turns:
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": turn["assistant"]})
        return messages
    except Exception:
        return []


def _save_exchange(session_id: str, user_message: str, assistant_message: str) -> None:
    try:
        _memory.save_turn(
            session_id=session_id,
            user=user_message,
            assistant=assistant_message,
        )
    except Exception:
        pass


if __name__ == "__main__":
    app.run()
