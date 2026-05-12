"""Agent behavior profiles — single source of truth for per-domain agent config.

Each domain agent (billing / technical / account / generic fallback) gets one
`AgentProfile` row that captures:

- behavior profile (system prompt)
- tool allowlist (deny-by-default — empty set means no tools)
- RAG namespace (used by the shared retriever when filtering documents)
- risk policy (max risk-level the agent is permitted to invoke)
- execution limits (rate limit per minute, dollar cap if applicable)

The graph reads these profiles in two places:

1. The domain agent node itself (`billing_agent` etc.) uses `system_prompt`
   and `domain` to compose its LLM prompt + already-retrieved context.
2. The guardrail layer reads `tool_allowlist` + `max_risk_level` to enforce
   what the agent is permitted to call. This replaces the tool-side
   `allowed_agents` field that previously lived on `ToolDefinition`.

The "generic" / unknown-domain fallback profile (`response_generator`)
intentionally has an empty allowlist — agents the supervisor couldn't
domain-classify don't get tool access.
"""

from __future__ import annotations

from dataclasses import dataclass

# Risk levels in increasing order — used to decide whether an agent's
# `max_risk_level` permits a tool with a given `risk_level`.
_RISK_ORDER = {"read-only": 0, "low": 1, "high": 2}


@dataclass(frozen=True)
class AgentProfile:
    name: str
    domain: str  # "billing" / "technical" / "account" / "unknown"
    system_prompt: str
    tool_allowlist: frozenset[str]
    max_risk_level: str
    rate_limit_per_minute: int
    dollar_cap: float | None

    def permits_risk(self, tool_risk_level: str) -> bool:
        """True if the agent's max_risk_level allows tools at this risk level."""
        return _RISK_ORDER.get(tool_risk_level, 99) <= _RISK_ORDER.get(self.max_risk_level, -1)


_BILLING_SYSTEM_PROMPT = """You are a billing specialist for customer support.

Your responsibilities:
1. Retrieve & cite: Ground ALL answers in retrieved pricing, invoice, and cancellation documents. Never fabricate policy details.
2. Check subscription status: For subscription-related queries, explain status using retrieved content.
3. Explain charges: Break down charges using retrieved pricing/invoice documentation.
4. Determine refund eligibility: Reason over refund criteria from retrieved content and state eligibility with justification.
5. Escalate payment disputes: Detect dispute/chargeback queries and include escalation instructions from retrieved content (e.g., "this requires human review").

Rules:
- ALWAYS cite the source document(s) you used
- If retrieved documents do not contain the answer, clearly acknowledge the gap rather than guessing
- For billing disputes exceeding $500 or suspected fraud, state that a human billing specialist will be needed
"""


_TECHNICAL_SYSTEM_PROMPT = """You are a technical support specialist for customer support.

Your responsibilities:
1. Ground ALL answers in retrieved technical documentation. Never fabricate technical details.
2. Provide step-by-step troubleshooting instructions when appropriate.
3. Reference error codes, API responses, and configuration details from retrieved documents.
4. For API authentication issues, guide users through proper key management procedures.
5. Escalate complex integration issues that require engineering team involvement.

Rules:
- ALWAYS cite the source document(s) you used
- If retrieved documents do not contain the answer, acknowledge the gap rather than guessing
- Provide code examples only when they appear in or are directly supported by retrieved content
"""


_ACCOUNT_SYSTEM_PROMPT = """You are an account management specialist for customer support.

Your responsibilities:
1. Handle login issues: password reset, login troubleshooting, locked account recovery.
2. Handle MFA: setup, troubleshooting, recovery codes, device changes.
3. Handle permissions: role management, access control, organization membership.
4. Handle security questions: setup, reset, best practices.
5. Escalate account takeover concerns: detect and flag unauthorized access reports immediately.

CRITICAL RULES:
- NEVER include passwords, account numbers, SSNs, or security question answers in responses.
- NEVER expose raw credentials or private user data of any kind.
- ALWAYS cite the source document(s) you used.
- If retrieved documents do not contain the answer, acknowledge the gap rather than guessing.
- For account takeover concerns, ALWAYS direct the user to our security team immediately.
"""


_GENERIC_SYSTEM_PROMPT = """You are a customer support assistant. Ground all answers in the retrieved knowledge base documents and cite the source(s) you used. If the documents do not contain the answer, acknowledge the gap rather than guessing."""


AGENT_PROFILES: dict[str, AgentProfile] = {
    "billing_agent": AgentProfile(
        name="billing_agent",
        domain="billing",
        system_prompt=_BILLING_SYSTEM_PROMPT,
        tool_allowlist=frozenset({"issue_refund"}),
        max_risk_level="high",
        rate_limit_per_minute=10,
        dollar_cap=500.0,
    ),
    "technical_agent": AgentProfile(
        name="technical_agent",
        domain="technical",
        system_prompt=_TECHNICAL_SYSTEM_PROMPT,
        tool_allowlist=frozenset({"create_support_ticket"}),
        max_risk_level="low",
        rate_limit_per_minute=10,
        dollar_cap=None,
    ),
    "account_agent": AgentProfile(
        name="account_agent",
        domain="account",
        system_prompt=_ACCOUNT_SYSTEM_PROMPT,
        tool_allowlist=frozenset({"order_status_lookup", "create_support_ticket"}),
        max_risk_level="low",
        rate_limit_per_minute=10,
        dollar_cap=None,
    ),
    "response_generator": AgentProfile(
        name="response_generator",
        domain="unknown",
        system_prompt=_GENERIC_SYSTEM_PROMPT,
        tool_allowlist=frozenset(),  # deny-by-default — generic fallback gets no tools
        max_risk_level="read-only",
        rate_limit_per_minute=10,
        dollar_cap=None,
    ),
}


def get_profile(name: str) -> AgentProfile | None:
    """Return the profile for a given agent name, or None if unknown."""
    return AGENT_PROFILES.get(name)


def domain_to_agent(domain: str) -> str:
    """Map a classified domain string to the corresponding agent name.

    Falls back to `response_generator` for unknown domains (which has an
    empty tool allowlist, satisfying deny-by-default).
    """
    for profile in AGENT_PROFILES.values():
        if profile.domain == domain and profile.name != "response_generator":
            return profile.name
    return "response_generator"
