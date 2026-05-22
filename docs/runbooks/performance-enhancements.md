# Performance Enhancements

Targeted latency-reduction opportunities for the LangGraph supervisor pipeline,
derived from analysis of Langfuse trace `8cbf69b6-6a37-4b9d-b4cd-0ed530566abe`
(query: *"How do I update my billing information?"*, total **9.893s**).

The trace is representative of the steady-state path:
`supervisor → security_check → retrieval_planner → multi_retriever → confidence_check (× retries) → billing_agent → validate_response`.

## Observed timeline

| Phase | Latency | % of total | Notes |
|---|---:|---:|---|
| `supervisor.classify_domain` (LLM) | 1.488s | 15% | Sequential before anything else |
| `security_check` | 0.001s | — | No-op |
| `retrieval_planner` #1 → `query_generator.expand` (LLM) | 1.467s | 15% | |
| `multi_retriever` #1 | 1.103s | 11% | avg_sim **0.421**, threshold 0.6 → retry |
| `retrieval_planner` #2 → `query_generator.expand` (LLM) | 1.548s | 16% | **Second LLM expansion** |
| `multi_retriever` #2 | 0.460s | 5% | avg_sim **0.438** → retry again |
| `retrieval_planner` #3 (skips LLM) + `multi_retriever` #3 | 0.216s | 2% | avg_sim **0.444**, max attempts hit |
| `billing_agent.llm` | 3.605s | 36% | 3,146 input tokens, ~158 output |

Roughly **8.1s of 9.9s is LLM time**, and **three LLM calls run before the
answer LLM ever starts.**

---

## Enhancements (ordered by ROI)

### 1. Recalibrate the retry-loop threshold (high impact, low risk)

The confidence threshold of **0.6** at [src/config.py:21](../../src/config.py#L21)
fires retries on virtually every query — observed `avg_similarity` stayed in
**0.42–0.44** across all three attempts in this trace. The retry loop is pure
overhead when retrieval is already as good as it's going to get.

Pick one or combine:

- Lower `confidence_threshold` to match the observed distribution (~**0.45**).
- Score on **top-k mean** (e.g. top 3) instead of `avg_similarity` over all
  results — tail noise drags the metric down. See
  [src/rag/confidence.py](../../src/rag/confidence.py).
- Add a *no-meaningful-improvement* early-exit: if attempt #2's score didn't
  rise by >X over #1, skip #3.

**Expected savings: ~2.0s** (eliminates 2nd planner LLM + 2nd & 3rd retrievers
on traces like this one).

### 2. Stop re-running the LLM query expansion on retry

[src/agents/retrieval_planner.py:32-37](../../src/agents/retrieval_planner.py#L32-L37)
calls `generate_search_queries(...)` again on attempt #2 to "broaden to all
3 domains" — but the *user intent* hasn't changed. Cache the attempt-1
expansion and just rewrite `target_domain` / `k`. Attempt #3 already does this
([src/agents/retrieval_planner.py:23-31](../../src/agents/retrieval_planner.py#L23-L31));
apply the same pattern to attempt #2.

**Expected savings: ~1.55s** on every retry-triggering trace.

### 3. Wire in the dead-code `_is_complex_query` gate

[src/rag/query_generator.py:57-62](../../src/rag/query_generator.py#L57-L62)
defines a heuristic specifically to skip LLM expansion for simple, single-facet
queries — but `generate_search_queries`
([src/rag/query_generator.py:74](../../src/rag/query_generator.py#L74)) invokes
the LLM unconditionally. The trace's query ("How do I update my billing
information?") is 6 words, single-facet, and should fast-path:

```python
def generate_search_queries(query_text, classified_domains):
    if not _is_complex_query(query_text):
        return [{"query": query_text, "target_domain": d, "aspect": "general"}
                for d in classified_domains]
    # else: existing LLM expansion path
```

**Expected savings: ~1.47s** on simple queries (likely the majority of
production traffic).

### 4. Parallelize `supervisor` with a speculative first retrieval

The first 2.96s is strictly serial: supervisor (1.49s) → planner LLM (1.47s) →
first vector search. The supervisor classification and a domain-agnostic
retrieval are independent. Fire
`retrieve_documents_unfiltered(query_text, k=5)` concurrently with
`supervisor.classify_domain`:

- If the classifier returns the same domain we'd have searched anyway, the
  speculative result is reused.
- If not, we re-retrieve. Expected-value math is strongly positive given the
  domain agreement rate.

**Expected savings: ~1.0s** on traces where the speculative hit lands.

### 5. Shrink the billing_agent (and peer agents) prompt

The HumanMessage in this trace was **13,890 chars / 3,146 input tokens**
because `merged_results` is concatenated verbatim at
[src/agents/billing_agent.py:37-45](../../src/agents/billing_agent.py#L37-L45).
On attempt #3 the agent is fed 15 docs to answer a one-paragraph billing FAQ.

- Cap to **top 5 by score**.
- Truncate each chunk to ~500 chars.
- Apply to `account_agent`, `technical_agent`, and `response_generator` in
  parallel — they all share the same pattern.

**Expected savings: ~1.0–1.5s** in the answer LLM stage (3.6s → ~2–2.5s).

### 6. Stream the final response

Even after the prompt shrink, `billing_agent.llm` will be ≥1.5s. Stream tokens
from the FastAPI endpoint through Streamlit so **time-to-first-token (~250ms)**
is what the user perceives, not full completion. This doesn't reduce wall-time
but materially improves UX.

Touches:
- [src/api/main.py](../../src/api/main.py) — switch `/query` from `POST` JSON
  return to a streaming response (Server-Sent Events or chunked).
- [src/frontend/api_client.py](../../src/frontend/api_client.py) — consume
  the stream.
- [src/agents/billing_agent.py](../../src/agents/billing_agent.py) (and peer
  agents) — `llm.stream(...)` instead of `llm.invoke(...)`.

### 7. Parallelize the retrieval inner loop

[src/agents/multi_retriever.py:28-44](../../src/agents/multi_retriever.py#L28-L44)
iterates `for sq in search_queries:` synchronously. With 2–3 queries this is
~460ms in this trace. Options:

- `asyncio.gather` on the per-query retrievals.
- Batch the embedding calls.
- Or rewrite as a single SQL `UNION ALL` against pgvector.

**Expected savings: ~200–300ms** when ≥2 queries are issued.

### 8. Use a faster classifier (or skip the LLM entirely for routing)

`supervisor` and `query_generator` are doing structured-output classification
on short text. Alternatives:

- A deterministic regex/keyword router (≤50ms vs ~1.5s).
- A small sentence-transformer + cosine to domain prototypes (~30ms on CPU).
- Keep the LLM only as a fallback when the cheap classifier's confidence is
  low.

If staying on an LLM, `claude-haiku-4-5` or `gpt-5-nano` will be noticeably
snappier than `gpt-4o-mini` for this size of task.

---

## Suggested rollout order

| Order | Change | Why first |
|---|---|---|
| 1 | #3 (wire `_is_complex_query`) | Isolated, dead-code activation, ~1.47s win |
| 2 | #2 (cached expansion on retry) | Self-contained, no behavioral change for simple traces |
| 3 | #1 (recalibrate threshold) | Requires picking a number — instrument first, then tune |
| 4 | #5 (shrink prompt) | Touches every domain agent; do once, applies broadly |
| 5 | #6 (streaming) | Larger change (API + UI), big perceived-latency win |
| 6 | #4 (parallel speculative retrieval) | Architectural — save until cheaper wins are in |
| 7 | #7, #8 | Polish |

## Projected end state

Implementing #1 + #2 + #3 + #5 alone:

| Item | Saving |
|---|---:|
| #2 — skip attempt-2 planner LLM | −1.55s |
| #1 — accept attempt-1 retrieval | −0.68s |
| #3 — skip attempt-1 planner LLM via fast-path | −1.47s |
| #5 — smaller billing prompt | ~−1.0s |
| **Total** | **~−4.7s** |

That takes a representative trace from **9.9s → ~5s** without touching the
supervisor or moving to streaming, and the saved latency is also saved cost
(3 of 4 LLM calls cut).

## How to validate after each change

1. Replay the seed query against the local API:
   `curl -s localhost:8000/query -H 'content-type: application/json' \
   -d '{"query_text":"How do I update my billing information?"}' | jq .metadata`
2. Open the new trace in Langfuse (project
   [`cmozupp9n065wad07lffz5u94`](https://us.cloud.langfuse.com)) and compare:
   - `agent.invoke` latency
   - count of `query_generator.expand` generations
   - count of `node.multi_retriever` spans
   - `billing_agent.llm` input token count
3. Repeat across a handful of canned queries with mixed domain + complexity
   to ensure no regression on the multi-facet path.
