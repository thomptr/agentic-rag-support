# Caching Enhancements

Detailed design notes for enhancement #2 in
[performance-enhancements.md](performance-enhancements.md): **stop re-running
the LLM query expansion on retry.** This runbook is the deeper "why and how"
behind that bullet.

Source trace: Langfuse `8cbf69b6-6a37-4b9d-b4cd-0ed530566abe` (query:
*"How do I update my billing information?"*).

## What the trace shows

Inside one `agent.invoke`, `query_generator.expand` ran **twice** as a child
of `retrieval_planner`:

| Span | Parent | Latency | Why it ran |
|---|---|---:|---|
| `query_generator.expand` #1 | `retrieval_planner` attempt 1 | 1.465s | First pass — expand the user question into N search variations focused on `classified_domains` (e.g. `["billing", "account"]`) |
| `query_generator.expand` #2 | `retrieval_planner` attempt 2 | 1.545s | Retry — same expansion, but now passing `_ALL_DOMAINS = ["billing", "technical", "account"]` to broaden the domain filter |

The diff between the two calls, from
[src/agents/retrieval_planner.py:32-43](../../src/agents/retrieval_planner.py#L32-L43):

```python
elif new_attempt == 2:
    search_queries = generate_search_queries(
        query_text=query_text,
        classified_domains=_ALL_DOMAINS,      # only this changed
    )
else:
    search_queries = generate_search_queries(
        query_text=query_text,                # same input both times
        classified_domains=classified_domains,
    )
```

`query_text` is identical between calls — the user hasn't re-typed anything.
The *only* difference is the domain list passed to the LLM. But the LLM's
actual job — produce 1–3 rephrasings of the user's question — doesn't depend
much on that list; the domain is just a tag attached to each generated
variation and is applied **later** as a filter by `multi_retriever`. We're
paying **~1.55s** to have an LLM re-rephrase the same sentence with a slightly
wider set of allowable tags.

## The real invariant the retry loop violates

> The prompt to the query-expansion LLM never changes meaningfully between
> attempts.

Attempt 2 isn't asking the LLM a new question; it's asking the same question
and expecting the *retrieval layer* to do something different (search more
domains, bigger `k`). The fix is to push that "do something different" logic
into `multi_retriever`'s domain filter and `k` parameter and stop dragging the
LLM along for the ride.

Once that's clear, "caching" is the small mechanical step that implements it:
stash attempt 1's result, branch on its presence, skip the LLM call.

## Two flavors of caching

### A. State-scoped reuse (high-impact)

Within a single `agent.invoke`, stash attempt 1's expansion in graph state and
short-circuit on retry. Two equivalent shapes:

**Shape 1 — reuse the same query strings, broaden their domain tag:**

```python
def retrieval_planner(state):
    cached = state.get("cached_search_queries")
    new_attempt = state.get("retrieval_attempt", 0) + 1

    if new_attempt == 2 and cached:
        # Reuse attempt-1 expansion, just open the domain filter wider.
        search_queries = [{**sq, "target_domain": "all"} for sq in cached]
    elif new_attempt >= 3:
        # Existing single-query "broad fallback" — already skips the LLM.
        search_queries = [{
            "query": state["query_text"],
            "target_domain": "all",
            "aspect": "broad fallback — no domain filter",
        }]
    else:
        # First attempt — pay the LLM cost once.
        search_queries = generate_search_queries(
            query_text=state["query_text"],
            classified_domains=state.get("classified_domains") or ["unknown"],
        )

    return {
        "search_queries": search_queries,
        "cached_search_queries": search_queries if new_attempt == 1 else cached,
        "retrieval_attempt": new_attempt,
        ...
    }
```

**Shape 2 — append a broader variation rather than relabeling.** Instead of
mutating `target_domain`, push an extra entry onto the cached list with the
raw `query_text` and `target_domain="all"`. Either shape eliminates the
second `query_generator.expand` span entirely.

**Saving: ~1.55s per retry-triggering trace.** No LLM cost on retries.
No tokens spent. No regression for the broaden-domains intent — the wider
search is still happening, it just happens at the `multi_retriever` layer
where it always belonged.

### B. Process-scoped cache (bonus, ~free)

Wrap `generate_search_queries` in `functools.lru_cache` keyed on
`(query_text, tuple(sorted(classified_domains)))`:

```python
from functools import lru_cache

# Note: lru_cache requires hashable args — pass a tuple, convert back inside.
@lru_cache(maxsize=1024)
def _cached_expansion(query_text: str, domains_key: tuple[str, ...]) -> tuple[dict, ...]:
    return tuple(_generate_search_queries_uncached(query_text, list(domains_key)))


def generate_search_queries(query_text: str, classified_domains: list[str]) -> list[dict]:
    return list(_cached_expansion(query_text, tuple(sorted(classified_domains))))
```

This wins whenever the **same question** hits the system again:

- Demo replays, the scenarios page, repeated test fixtures
- Real users rephrasing identically ("How do I cancel?" being asked many times)
- The same query reused within a session
- CI runs that exercise canned queries

**Cost:** a small in-memory dict. **Risk:** the LLM is non-deterministic, so
cached output is "frozen" — fine for a query expander (deterministic enough,
and the downstream retriever is what matters), but you'd avoid this pattern
on creative-generation paths like the final agent response.

### Why both, not just one

| Scenario | (A) alone | (B) alone | Both |
|---|:-:|:-:|:-:|
| Fresh query, first attempt | pay 1.47s | pay 1.47s | pay 1.47s |
| Fresh query, retry within same invoke | **skipped** | pay 1.55s | **skipped** |
| Repeat of a previous query, first attempt | pay 1.47s | **skipped (cache hit)** | **skipped** |
| Repeat of a previous query, retry | **skipped** | **skipped** | **skipped** |

(A) alone fixes the retry case but does nothing for the steady-state
first-attempt 1.47s when the same query has been seen before. (B) alone does
nothing for a brand-new query on its first invocation. Together, the first
attempt of a fresh query pays 1.47s once, the retry within that same
invocation skips the LLM via (A), and any subsequent invocation of the same
query hits (B) and skips the LLM entirely from the start.

## Rollout

Suggested order, low risk → broader behavior change:

1. **Add (B) — `lru_cache` on `generate_search_queries`.** Single-file change
   in [src/rag/query_generator.py](../../src/rag/query_generator.py). No state
   shape change. Worst case it's a no-op for unique queries.
2. **Add (A) — cached_search_queries in state.** Touches
   [src/agents/retrieval_planner.py](../../src/agents/retrieval_planner.py)
   and the state schema in
   [src/graph/state.py](../../src/graph/state.py) (add `cached_search_queries:
   list[dict] | None`). Update
   [tests/unit/test_retrieval_planner.py](../../tests/unit/test_retrieval_planner.py)
   to assert the LLM is **not** called on attempt 2 when cache is present.

## Validation

After implementing, replay the seed query and inspect the trace in Langfuse:

```bash
curl -s localhost:8000/query -H 'content-type: application/json' \
  -d '{"query_text":"How do I update my billing information?"}' | jq .metadata
```

The new trace should show:

- Exactly **one** `query_generator.expand` generation (down from two), or
  **zero** if (B) was also implemented and the query has been seen before.
- `node.retrieval_planner` latency on attempt 2 should drop to ~0s
  (matching attempt 3's current latency).
- Total `agent.invoke` latency should drop by ~1.5s on the retry path.

Confirm no behavioral regression on multi-facet queries by replaying a
deliberately complex prompt (e.g. *"My API key got revoked after I cancelled
my plan — can I export my team's data first?"*) and verifying it still
generates multiple distinct search variations on attempt 1.
