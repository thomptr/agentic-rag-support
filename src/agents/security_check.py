import re
import time

from langgraph.types import Command

from src.graph.state import SupportGraphState
from src.observability.logger import log_security_check

_TAKEOVER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("hacked_account", re.compile(r"\b(?:hacked|hack(?:ing)?)\b.*\b(?:account|profile)\b", re.I)),
    (
        "hacked_account",
        re.compile(r"\b(?:account|profile)\b.*\b(?:hacked|compromised|stolen)\b", re.I),
    ),
    ("unauthorized_access", re.compile(r"\bunauthorized\b.*\b(?:access|login|change)\b", re.I)),
    (
        "someone_logged_in",
        re.compile(r"\bsomeone\b.*\b(?:logged in|accessed|got into|signed in)\b", re.I),
    ),
    (
        "not_me_change",
        re.compile(r"\b(?:didn't|did not|i didnt)\b.*\b(?:make|do|sign|log)\b", re.I),
    ),
    ("compromised", re.compile(r"\b(?:compromised|breach(?:ed)?)\b", re.I)),
    ("account_stolen", re.compile(r"\baccount\b.*\bstolen\b", re.I)),
)


def _detect_signals(query_text: str) -> list[dict]:
    """Run rule-based pattern matching against the query text. Returns matched signals."""
    signals: list[dict] = []
    for signal_name, pattern in _TAKEOVER_PATTERNS:
        match = pattern.search(query_text)
        if match:
            signals.append(
                {
                    "name": "account_takeover",
                    "matched_pattern": match.group(0),
                    "severity": "block",
                    "action": "escalate",
                }
            )
            # Stop after the first takeover hit; one signal is enough to escalate.
            break
        # Tag non-blocking variants by signal_name even on miss? No — only emit on match.
        del signal_name
    return signals


def security_check(state: SupportGraphState) -> Command:
    """Policy gate that runs after the supervisor and before retrieval.

    Detects sensitive-query categories (currently account takeover) using fast rule-based
    matching. When a blocking signal fires, routes to escalation_handler so the user reaches
    the security team without retrieval or generation cost.
    """
    query_text = state["query_text"]
    run_id = state["run_id"]

    start = time.perf_counter()
    signals = _detect_signals(query_text)
    latency_ms = (time.perf_counter() - start) * 1000

    blocking = next((s for s in signals if s["severity"] == "block"), None)

    if blocking is not None:
        action = "escalate"
        check_event = log_security_check(
            run_id=run_id,
            signals=signals,
            action=action,
            latency_ms=latency_ms,
        )
        return Command(
            goto="escalation_handler",
            update={
                "security_signals": signals,
                "escalation_required": True,
                "escalation_reason": blocking["name"],
                "current_node": "escalation_handler",
                "log_events": [check_event],
            },
        )

    action = "continue"
    check_event = log_security_check(
        run_id=run_id,
        signals=signals,
        action=action,
        latency_ms=latency_ms,
    )
    return Command(
        goto="retrieval_planner",
        update={
            "security_signals": signals,
            "escalation_required": False,
            "log_events": [check_event],
        },
    )
