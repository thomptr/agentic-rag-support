"""Unit tests for the Cognito M2M JWT cache.

TDD red — references `src.api.cognito_jwt_cache` (does not exist until T040).

State machine (from data-model.md):
    EMPTY → (fetch) → FRESH → (exp - now < 60s) → STALE → (refresh) → FRESH
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

try:
    from src.api.cognito_jwt_cache import JWTCache, TokenFetchError
except ImportError as exc:
    pytest.skip(f"red — implementation missing: {exc}", allow_module_level=True)


def _fake_token(exp_in_seconds: int = 3600) -> dict:
    return {
        "access_token": f"jwt-{exp_in_seconds}",
        "expires_in": exp_in_seconds,
        "token_type": "Bearer",
    }


class TestJWTCacheStateMachine:
    def test_initial_state_is_empty(self):
        cache = JWTCache(token_url="https://x", client_id="c", client_secret="s", scope="t/s")
        assert cache.state() == "EMPTY"

    def test_first_get_transitions_empty_to_fresh(self):
        cache = JWTCache(token_url="https://x", client_id="c", client_secret="s", scope="t/s")
        with patch.object(cache, "_request_token", return_value=_fake_token()):
            token = cache.get()
        assert token == "jwt-3600"
        assert cache.state() == "FRESH"

    def test_subsequent_get_reuses_fresh_token(self):
        cache = JWTCache(token_url="https://x", client_id="c", client_secret="s", scope="t/s")
        with patch.object(cache, "_request_token", return_value=_fake_token()) as fetch:
            cache.get()
            cache.get()
            cache.get()
        assert fetch.call_count == 1

    def test_stale_token_triggers_refresh(self):
        cache = JWTCache(token_url="https://x", client_id="c", client_secret="s", scope="t/s")
        # First fetch returns a token that's already near expiry (10s window),
        # the refresh threshold is 60s so the next get() must refetch.
        with patch.object(cache, "_request_token", side_effect=[_fake_token(10), _fake_token()]):
            cache.get()
            assert cache.state() == "STALE"
            cache.get()
            assert cache.state() == "FRESH"

    def test_explicit_invalidate_sets_empty(self):
        cache = JWTCache(token_url="https://x", client_id="c", client_secret="s", scope="t/s")
        with patch.object(cache, "_request_token", return_value=_fake_token()):
            cache.get()
        cache.invalidate()
        assert cache.state() == "EMPTY"

    def test_token_fetch_error_raises_typed_exception(self):
        cache = JWTCache(token_url="https://x", client_id="c", client_secret="s", scope="t/s")
        with patch.object(cache, "_request_token", side_effect=TokenFetchError("401")):
            with pytest.raises(TokenFetchError):
                cache.get()
        assert cache.state() == "EMPTY"

    def test_refresh_window_is_60_seconds(self):
        """Tokens with >60s remaining are FRESH; <=60s are STALE."""
        cache = JWTCache(token_url="https://x", client_id="c", client_secret="s", scope="t/s")
        with patch.object(cache, "_request_token", return_value=_fake_token(120)):
            cache.get()
            assert cache.state() == "FRESH"
        # Fast-forward time so only 30s remain on the token.
        with patch.object(time, "time", return_value=time.time() + 90):
            assert cache.state() == "STALE"
