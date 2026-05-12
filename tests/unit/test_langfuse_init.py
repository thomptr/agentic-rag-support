"""Unit tests for `src.observability.langfuse_init`.

These run with NO Langfuse credentials, so `_LANGFUSE` is None and every
helper must no-op cleanly. The point is to lock the "absent SDK or absent
creds is non-fatal" contract — if a future refactor accidentally raises
inside one of these helpers, agent traffic breaks.
"""

from __future__ import annotations

from src.observability import langfuse_init


def test_is_enabled_returns_false_without_credentials():
    # Test env has no LANGFUSE_*_REF, so init returned None.
    assert langfuse_init.is_enabled() is False


def test_trace_context_yields_none_and_doesnt_raise():
    with langfuse_init.trace(name="test", input_payload={"x": 1}) as t:
        assert t is None


def test_span_yields_null_span_outside_trace():
    with langfuse_init.span(name="test_span") as sp:
        # Null span must support the same surface real spans expose.
        sp.update(output={"foo": "bar"})
        sp.end()
        # Attribute assignment is silently ignored.
        sp.metadata = {"y": 2}


def test_generation_yields_null_span_outside_trace():
    with langfuse_init.generation(
        name="test_gen", model="gpt-4o-mini", input_payload=[{"role": "user", "content": "hi"}]
    ) as gen:
        gen.update(output="ok")
        gen.end()


def test_current_trace_meta_synthesizes_uuids_when_no_trace_active():
    meta = langfuse_init.current_trace_meta(session_id="s-1", run_id="r-1")
    # Required fields per lambdas/shared/tracing.py — Lambdas reject empty/missing.
    for field in ("trace_id", "parent_span_id", "session_id", "run_id"):
        assert isinstance(meta[field], str) and meta[field]
    assert meta["session_id"] == "s-1"
    assert meta["run_id"] == "r-1"


def test_null_span_supports_setattr_and_methods():
    null = langfuse_init._NullSpan()
    null.update(output={"x": 1})
    null.end(output="done")
    null.id = "should-be-ignored"
    assert null.id == ""  # class attribute unchanged
