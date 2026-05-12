"""Lock the redaction key list for `lambdas.shared.langfuse_client.redact`.

If a new sensitive field name appears anywhere in payloads sent to Langfuse,
add it to `REDACT_KEYS` and extend `EXPECTED_REDACT_KEYS` here. The test fails
fast on drift so the redaction surface stays auditable.
"""

from __future__ import annotations

import pytest

from lambdas.shared.langfuse_client import REDACT_KEYS, REDACTION_PLACEHOLDER, redact

EXPECTED_REDACT_KEYS = {
    "password",
    "card_number",
    "cvv",
    "secret",
    "client_secret",
    "authorization",
}


def test_redact_key_list_matches_expected():
    """Catch unauthorized changes to the redacted-field set."""
    assert set(REDACT_KEYS) == EXPECTED_REDACT_KEYS


@pytest.mark.parametrize("key", sorted(EXPECTED_REDACT_KEYS))
def test_redact_replaces_each_known_sensitive_key(key):
    payload = {key: "leakable-value"}
    assert redact(payload) == {key: REDACTION_PLACEHOLDER}


def test_redact_is_case_insensitive():
    payload = {"Password": "abc", "AUTHORIZATION": "Bearer xyz"}
    out = redact(payload)
    assert out["Password"] == REDACTION_PLACEHOLDER
    assert out["AUTHORIZATION"] == REDACTION_PLACEHOLDER


def test_redact_preserves_non_sensitive_fields():
    payload = {"order_id": "ORD-1", "amount": 49.99, "items": [{"sku": "X"}]}
    out = redact(payload)
    assert out == payload


def test_redact_recurses_into_nested_dicts_and_lists():
    payload = {
        "outer": {
            "inner": {"password": "p", "ok": "yes"},
            "list": [{"cvv": "123"}, {"label": "fine"}],
        }
    }
    out = redact(payload)
    assert out["outer"]["inner"] == {"password": REDACTION_PLACEHOLDER, "ok": "yes"}
    assert out["outer"]["list"][0] == {"cvv": REDACTION_PLACEHOLDER}
    assert out["outer"]["list"][1] == {"label": "fine"}


def test_redact_handles_primitives():
    assert redact("hello") == "hello"
    assert redact(42) == 42
    assert redact(None) is None
