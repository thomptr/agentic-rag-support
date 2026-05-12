"""Structured audit emitter — JSON lines to stdout for CloudWatch ingestion.

Mirrors the agent-side `src/tools/audit.py` event shapes so a single log query
can correlate in-process audit events with Lambda-side audit events.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any


def _emit(event: dict[str, Any]) -> None:
    event.setdefault("ts", time.time())
    print(json.dumps(event, default=str), file=sys.stdout)


def log_tool_attempt(
    *, tool_name: str, parameters: dict[str, Any], session_id: str, trace_id: str
) -> None:
    _emit(
        {
            "event": "tool.attempt",
            "tool_name": tool_name,
            "parameters": parameters,
            "session_id": session_id,
            "trace_id": trace_id,
        }
    )


def log_tool_success(
    *,
    tool_name: str,
    result: dict[str, Any],
    session_id: str,
    trace_id: str,
    duration_ms: float,
) -> None:
    _emit(
        {
            "event": "tool.success",
            "tool_name": tool_name,
            "result": result,
            "session_id": session_id,
            "trace_id": trace_id,
            "duration_ms": duration_ms,
        }
    )


def log_tool_failed(
    *,
    tool_name: str,
    error_code: str,
    error_message: str,
    session_id: str,
    trace_id: str,
    duration_ms: float,
) -> None:
    _emit(
        {
            "event": "tool.failed",
            "tool_name": tool_name,
            "error_code": error_code,
            "error_message": error_message,
            "session_id": session_id,
            "trace_id": trace_id,
            "duration_ms": duration_ms,
        }
    )
