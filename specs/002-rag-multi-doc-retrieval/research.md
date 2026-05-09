# Research: RAG Multi-Document Retrieval

**Branch**: `002-rag-multi-doc-retrieval` | **Date**: 2026-05-09

## 1. Vector Store: PostgreSQL + pgvector (Confirmed)

**Decision**: Continue using PostgreSQL 16 + pgvector (from 001).

**Rationale**: The user explicitly confirmed pgvector. The existing single-collection design with `domain` metadata filtering already supports cross-domain retrieval — remove the domain filter to search across all domains, or supply multiple domain values. No schema migration needed.

**Alternatives considered**:
- ChromaDB / FAISS (constitution placeholder): Rejected — pgvector already operational, single-DB simplicity per Principle V.
- Separate collections per domain: Rejected — single collection with metadata filter is simpler and already working.

**Cross-domain query pattern**:
```python
# Single domain (existing)
vector_store.similarity_search_with_relevance_scores(query, k=5, filter={"domain": "billing"})

# Multi-domain (new)
vector_store.similarity_search_with_relevance_scores(query, k=5, filter={"domain": {"$in": ["billing", "account"]}})

# All domains (fallback for adaptive retry)
vector_store.similarity_search_with_relevance_scores(query, k=10)  # no filter
```

## 2. Multi-Query Retrieval

**Decision**: Custom multi-query generation using Claude, not LangChain's `MultiQueryRetriever`.

**Rationale**: LangChain's `MultiQueryRetriever` has a known issue where metadata filters are ignored when used with `PGVectorStore` (GitHub issue #5704). Since domain metadata filtering is critical for cross-domain retrieval, using the built-in class would silently break domain-scoped search. A custom implementation using Claude to generate query variations gives full control over domain targeting and is straightforward (one LLM call to generate 2-3 query reformulations).

**Alternatives considered**:
- LangChain `MultiQueryRetriever`: Rejected — metadata filter bug with PGVectorStore.
- Query expansion via keyword extraction: Rejected — LLM-based reformulation produces more semantically diverse queries.
- HyDE (Hypothetical Document Embeddings): Rejected — adds complexity beyond POC scope (Principle V).

**Implementation pattern**:
```python
# Prompt Claude to generate query variations
queries = generate_search_queries(original_query, classified_domains)
# Returns: [{"query": "...", "target_domain": "billing"}, {"query": "...", "target_domain": "account"}]
```

## 3. RAGAS Framework for RAG Evaluation

**Decision**: Use RAGAS (`ragas` PyPI package) for evaluating retrieval and response quality in the test suite.

**Rationale**: The user explicitly requested RAGAS for proving grounded support answers. RAGAS provides four core metrics that directly map to the feature's success criteria:

| RAGAS Metric | Maps To | What It Proves |
|---|---|---|
| **Faithfulness** | SC-001, FR-009 | Every claim in the response can be traced to retrieved documents (proves grounding) |
| **Answer Relevancy** | SC-001 | The response actually addresses the user's question |
| **Context Precision** | SC-002 | Retrieved documents are ranked correctly — relevant docs appear first |
| **Context Recall** | SC-002, SC-004 | The retrieval step found all the documents needed to answer the question |

**Integration approach**: RAGAS's `evaluate()` function with `in_ci=True` for reproducible results in pytest. Evaluation datasets are hand-curated from the knowledge base with known ground-truth answers.

**Alternatives considered**:
- Custom metric functions: Rejected — RAGAS is the industry standard; no reason to reimplement.
- DeepEval: Rejected — RAGAS has better LangChain integration and the user specifically requested it.
- Manual evaluation only: Rejected — not reproducible, not CI-friendly.

**Key dependency**: RAGAS requires an LLM for metric computation (uses it to judge faithfulness, relevancy, etc.). Will use Claude via the existing `ChatAnthropic` configuration.

## 4. Adaptive Retrieval (Confidence-Based Retry)

**Decision**: Score retrieval results by average similarity score and document count. Retry with relaxed parameters if below threshold.

**Rationale**: Simplest approach that satisfies FR-006/FR-007/FR-008. The similarity scores are already returned by pgvector. A confidence assessment is a simple function (no LLM call needed) that checks:
1. Are there enough results? (minimum document count)
2. Are the top results relevant? (average similarity score above threshold)

**Retry strategy**:
- Attempt 1: Standard retrieval (domain-filtered, k=5)
- Attempt 2: Increase k to 10, broaden domain filter
- Attempt 3: Remove domain filter entirely, k=15
- After 3 attempts: Acknowledge knowledge gap (FR-009)

**Alternatives considered**:
- LLM-based confidence scoring: Rejected — adds latency and cost. Similarity scores are sufficient for POC.
- Embedding-based query quality check: Rejected — over-engineered for POC scope.

## 5. Graph Architecture Change

**Decision**: Replace per-domain worker agents with a unified retrieval-generation pipeline.

**Rationale**: The existing pattern (3 nearly-identical worker functions that each do retrieve + generate) doesn't support cross-domain retrieval. Rather than adding cross-domain logic to each worker, a unified pipeline eliminates duplication and naturally supports both single-domain and multi-domain queries:

```
START → supervisor → retrieval_planner → multi_retriever → confidence_check → response_generator → validate_response → END
                                              ↑                    |
                                              └────── retry ───────┘
                                        fallback_handler → END
```

**Key changes from 001 graph**:
- `supervisor`: Now returns `classified_domains: list[str]` (can be 1 or many)
- `retrieval_planner`: New node — generates search queries per domain
- `multi_retriever`: New node — executes queries, deduplicates, ranks
- `confidence_check`: New node — evaluates quality, decides retry or continue
- `response_generator`: New node — replaces per-domain workers for response generation
- `billing_agent`, `technical_agent`, `account_agent`: Removed (replaced by unified pipeline)

**Single-domain performance** (FR-011): The same pipeline handles single-domain queries — retrieval_planner generates queries for one domain, multi_retriever searches only that domain. No special-casing needed.

**Alternatives considered**:
- Keep per-domain workers + add cross-domain orchestrator: Rejected — duplicates retrieval logic, harder to maintain, violates Principle V.
- Parallel domain retrieval via LangGraph `Send()`: Considered for future, but sequential retrieval is simpler and sufficient for POC scope with 3 domains.

## 6. Result Merging and Deduplication

**Decision**: Deduplicate by document chunk content hash, then rank by similarity score, capped at 20 documents (spec assumption).

**Rationale**: Multi-query and cross-domain retrieval can return duplicate chunks. Deduplication by content hash is exact and cheap. Ranking by similarity score after dedup ensures the best results surface. The 20-document cap matches the spec's assumption about context window capacity.

**Alternatives considered**:
- Reciprocal Rank Fusion (RRF): Rejected — adds complexity. Simple score-based ranking is sufficient when all scores come from the same embedding model and vector store.
- Maximal Marginal Relevance (MMR): Considered for diversity, but pgvector's default similarity search is adequate for POC.
