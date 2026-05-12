"""HTTP client wrapping the FastAPI backend for the Streamlit frontend."""

import os

import httpx

# In ECS the task def sets API_URL to the ALB's HTTP endpoint; local dev
# defaults to a uvicorn on 8000.
BACKEND_URL = os.environ.get("API_URL", "http://localhost:8000")
REQUEST_TIMEOUT = 30

_client = httpx.Client(base_url=BACKEND_URL, timeout=REQUEST_TIMEOUT)


def send_query(
    query_text: str,
    session_id: str | None = None,
    guardrails_enabled: bool | None = None,
    model_override: str | None = None,
) -> dict:
    payload: dict = {"query_text": query_text}
    if session_id is not None:
        payload["session_id"] = session_id
    if guardrails_enabled is not None:
        payload["guardrails_enabled"] = guardrails_enabled
    if model_override is not None:
        payload["model_override"] = model_override

    response = _client.post("/query", json=payload)
    response.raise_for_status()
    return response.json()


def get_approvals() -> list[dict]:
    response = _client.get("/approvals")
    response.raise_for_status()
    return response.json().get("approvals", [])


def approve_action(
    approval_id: str, reviewer: str = "frontend", reason: str = "Approved via UI"
) -> dict:
    response = _client.post(
        f"/approvals/{approval_id}/approve",
        json={"reviewer": reviewer, "reason": reason},
    )
    response.raise_for_status()
    return response.json()


def reject_action(
    approval_id: str, reviewer: str = "frontend", reason: str = "Rejected via UI"
) -> dict:
    response = _client.post(
        f"/approvals/{approval_id}/reject",
        json={"reviewer": reviewer, "reason": reason},
    )
    response.raise_for_status()
    return response.json()


def health_check() -> bool:
    try:
        response = _client.get("/health")
        response.raise_for_status()
        return True
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
        return False
