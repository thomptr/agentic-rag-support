"""Preset demo scenarios and customer profiles."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PresetScenario:
    id: str
    category: str
    title: str
    query_text: str
    description: str


@dataclass(frozen=True)
class CustomerProfile:
    id: str
    name: str
    description: str


SCENARIOS: list[PresetScenario] = [
    # Billing
    PresetScenario(
        id="billing-1",
        category="Billing",
        title="Update billing info",
        query_text="How do I update my billing information?",
        description="Customer wants to change their payment details",
    ),
    PresetScenario(
        id="billing-2",
        category="Billing",
        title="Invoice dispute",
        query_text="I was charged twice on my last invoice. Can you help?",
        description="Customer reports a duplicate charge",
    ),
    PresetScenario(
        id="billing-3",
        category="Billing",
        title="Payment methods",
        query_text="What payment methods do you accept?",
        description="Customer asking about supported payment options",
    ),
    # Technical
    PresetScenario(
        id="technical-1",
        category="Technical",
        title="API rate limits",
        query_text="What are the API rate limits for the pro plan?",
        description="Developer asking about rate limiting on the pro tier",
    ),
    PresetScenario(
        id="technical-2",
        category="Technical",
        title="Webhook integration",
        query_text="How do I set up the webhook integration?",
        description="Developer setting up event notifications",
    ),
    PresetScenario(
        id="technical-3",
        category="Technical",
        title="Error troubleshooting",
        query_text="I'm getting a 502 error when calling the API.",
        description="Developer troubleshooting a gateway error",
    ),
    # Account
    PresetScenario(
        id="account-1",
        category="Account",
        title="Reset password",
        query_text="How do I reset my password?",
        description="User locked out of their account",
    ),
    PresetScenario(
        id="account-2",
        category="Account",
        title="Account permissions",
        query_text="How do I add a new team member to my account?",
        description="Admin managing team access",
    ),
    PresetScenario(
        id="account-3",
        category="Account",
        title="Cancel subscription",
        query_text="I want to cancel my subscription.",
        description="Customer requesting cancellation",
    ),
]

CUSTOMER_PROFILES: list[CustomerProfile] = [
    CustomerProfile(
        id="cust-001",
        name="Acme Corp",
        description="Enterprise customer, billing-heavy",
    ),
    CustomerProfile(
        id="cust-002",
        name="Startup Inc",
        description="Small team, technical questions",
    ),
    CustomerProfile(
        id="cust-003",
        name="Demo User",
        description="Generic demo identity",
    ),
]

CATEGORIES = sorted({s.category for s in SCENARIOS})

SCENARIOS_BY_CATEGORY: dict[str, list[PresetScenario]] = {
    category: [s for s in SCENARIOS if s.category == category] for category in CATEGORIES
}
