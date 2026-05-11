"""Response envelope helpers for executor-tool Lambdas.

The shape is defined in
`specs/005-aws-agentcore-deployment/contracts/tool-lambda.md`. Use these
helpers so every Lambda returns the same fields and the agent's parser
doesn't need tool-specific branches.
"""

from __future__ import annotations

from typing import Any

ErrorCode = str  # one of: invalid_parameters, missing_trace_context, wrong_tool_target,
#                                business_rule_violation, external_dependency_unavailable,
#                                internal_error


def success(result: dict[str, Any], trace_id: str) -> dict[str, Any]:
    return {
        "status": "success",
        "result": result,
        "trace_id": trace_id,
    }


def error(
    code: ErrorCode,
    message: str,
    trace_id: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": "error",
        "error_code": code,
        "error_message": message,
        "trace_id": trace_id,
    }
    if details is not None:
        body["details"] = details
    return body
