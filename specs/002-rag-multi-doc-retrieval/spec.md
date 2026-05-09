# Feature Specification: RAG Multi-Document Retrieval

**Feature Branch**: `002-rag-multi-doc-retrieval`
**Created**: 2026-05-09
**Status**: Draft
**Input**: User description: "Create a RAG knowledge base with multi-document retrieval"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cross-Domain Query Resolution (Priority: P1)

A customer submits a query that spans multiple support domains (e.g., a billing issue that also involves account access). Instead of forcing the system to pick a single domain and potentially miss relevant context, the system retrieves documents from all applicable domains and produces a unified answer with citations from each.

**Why this priority**: This is the core value proposition. The existing system routes ambiguous queries to a single domain, losing relevant context from other domains. Cross-domain retrieval directly improves answer quality for the most difficult customer queries — the ones most likely to escalate.

**Independent Test**: Submit a query like "I was charged twice and now my account is locked" and verify: (1) documents are retrieved from both billing and account domains, (2) the response addresses both concerns, (3) citations reference sources from multiple domains.

**Acceptance Scenarios**:

1. **Given** a query touching two domains (e.g., billing and account), **When** the system processes the query, **Then** it retrieves relevant documents from both domains and the response includes citations from each.
2. **Given** a query touching all three domains, **When** the system processes the query, **Then** it retrieves from all three and synthesizes a coherent unified response.
3. **Given** a single-domain query, **When** the system processes it, **Then** retrieval behavior is unchanged from the current single-domain approach (no regression).

---

### User Story 2 - Multi-Query Retrieval for Improved Recall (Priority: P2)

For complex or lengthy customer questions, a single search query may not capture all relevant documents. The system generates multiple search variations from the original question to improve recall — finding documents that a single query would miss.

**Why this priority**: Improves answer completeness for nuanced questions. A customer asking "What happens to my data if I cancel mid-cycle and haven't exported my reports?" needs documents about cancellation terms, data retention, and export procedures. A single similarity search may only match one of these topics.

**Independent Test**: Submit a complex multi-faceted query and verify: (1) the system generates at least two distinct search queries, (2) the combined result set covers more relevant documents than a single query alone, (3) duplicate documents are deduplicated before being passed to the response generator.

**Acceptance Scenarios**:

1. **Given** a complex query with multiple facets, **When** the system processes it, **Then** it generates multiple search queries targeting different aspects of the question.
2. **Given** multiple search queries that return overlapping results, **When** results are combined, **Then** duplicate documents are removed and the final set is ranked by relevance.
3. **Given** a simple, single-facet query, **When** the system processes it, **Then** it may use a single search query without unnecessary expansion (no forced multi-query overhead).

---

### User Story 3 - Confidence-Based Adaptive Retrieval (Priority: P3)

When initial retrieval results are low quality (low similarity scores or too few relevant documents), the system automatically adjusts its retrieval strategy — broadening the search, relaxing domain filters, or increasing the number of results retrieved — rather than generating an answer from weak evidence.

**Why this priority**: Prevents the system from confidently answering based on marginally relevant documents. Adaptive retrieval is a quality safety net that reduces hallucination risk when the knowledge base has gaps.

**Independent Test**: Submit a query on a topic with sparse knowledge base coverage and verify: (1) the system detects low-confidence initial results, (2) it retries with adjusted parameters, (3) if results remain insufficient, it acknowledges the gap rather than generating a poorly-grounded answer.

**Acceptance Scenarios**:

1. **Given** a query where initial retrieval returns results below the confidence threshold, **When** the system evaluates retrieval quality, **Then** it performs a follow-up retrieval with adjusted parameters (e.g., increased result count or relaxed filters).
2. **Given** a query where even adjusted retrieval returns insufficient results, **When** the system evaluates the retry results, **Then** it acknowledges the knowledge gap in the response rather than generating a weakly-grounded answer.
3. **Given** a query where initial retrieval returns high-confidence results, **When** the system evaluates retrieval quality, **Then** no retry is performed and processing continues normally.

---

### User Story 4 - Sensitive Query Escalation (Priority: P2)

When a customer query indicates an active security incident (account takeover, suspected fraud, unauthorized access), the system must bypass normal retrieval and route the user to the security/incident-response team immediately, without consuming retrieval or generation cost. This re-homes escalation behavior previously embedded in the deprecated per-domain worker agents.

**Why this priority**: Active security incidents have different latency and correctness requirements than informational queries. Pulling RAG documents and synthesizing an answer for "I think someone hacked my account" is wasteful and potentially harmful — the user needs to be routed to a human responder, not given a generated explanation. Centralizing the policy gate also gives future policy concerns (PII redaction, plan-tier gating, prompt-injection guards) a single place to live.

**Independent Test**: Submit a query containing account-takeover phrasing (e.g., "Someone logged into my account without my permission") and verify: (1) retrieval is *not* invoked, (2) the response routes the user to the security team with clear next steps, (3) an `escalation_triggered` log event is emitted with the originating policy signals, (4) total latency is bounded by the policy check rather than retrieval + generation.

**Acceptance Scenarios**:

1. **Given** a query containing account-takeover keywords, **When** the system processes the query, **Then** the policy node detects the signal, the graph routes to an escalation handler, and no retrieval is performed.
2. **Given** a query with no sensitive-policy signals, **When** the system processes the query, **Then** the policy node passes through to retrieval with no observable change in behavior compared to the pre-policy graph.
3. **Given** a sensitive query that escalates, **When** the response is returned, **Then** it includes explicit security-team contact instructions and an `escalation_triggered` event is logged with the matching signal.

---

### Edge Cases

- What happens when a cross-domain query retrieves documents that contain contradictory information across domains?
- How does the system handle a query where multi-query expansion produces zero additional relevant results beyond the original query?
- What happens when adaptive retrieval retry exceeds a maximum retry limit?
- How does the system handle a query that matches no documents in any domain, even after adaptive expansion?
- What happens when the combined result set from multi-query retrieval exceeds the context window capacity of the response generator?
- How does the policy node handle ambiguous phrasing that *could* be a security incident but is more likely informational (e.g., "How do I tell if my account was hacked?")?
- What happens when multiple policy signals fire on the same query (e.g., takeover + suspected fraud)?
- How are false-positive escalations recovered — can the user reroute to normal retrieval without restarting the conversation?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support retrieving documents from multiple knowledge base domains in a single query processing cycle
- **FR-002**: System MUST merge and deduplicate documents retrieved from multiple domains or multiple queries before passing them to the response generator
- **FR-003**: System MUST preserve domain attribution in citations so the user can see which domain each cited document belongs to
- **FR-004**: System MUST generate multiple search query variations from a single complex user question to improve document recall
- **FR-005**: System MUST rank the combined result set by relevance after merging results from multiple queries or domains
- **FR-006**: System MUST evaluate retrieval confidence based on similarity scores of returned documents
- **FR-007**: System MUST retry retrieval with adjusted parameters when initial results fall below the confidence threshold
- **FR-008**: System MUST cap the maximum number of retrieval retries to prevent unbounded processing
- **FR-009**: System MUST acknowledge knowledge gaps explicitly when retrieval results remain insufficient after retries, rather than generating weakly-grounded responses
- **FR-010**: System MUST log all retrieval attempts (initial and retries) with their parameters and result counts for observability
- **FR-011**: System MUST not regress single-domain query performance — simple queries that clearly belong to one domain should retrieve as efficiently as before
- **FR-012**: System MUST limit the total number of documents passed to the response generator to avoid exceeding context capacity
- **FR-013**: System MUST evaluate every classifiable query against a policy gate *before* invoking retrieval, so sensitive queries can short-circuit the pipeline
- **FR-014**: System MUST detect account-takeover phrasing (and other sensitive-query categories defined in policy) using rule-based signals; LLM-assisted classification MAY supplement rules but MUST NOT be the sole signal source
- **FR-015**: System MUST route detected sensitive queries to an escalation handler that produces a security-team-routing response without invoking retrieval or generation against the knowledge base
- **FR-016**: System MUST log every policy evaluation outcome (signal name, matched pattern, action taken) for audit and false-positive analysis
- **FR-017**: Policy gate MUST be composable — adding a new policy category (e.g., PII redaction, plan-tier gating) MUST NOT require changes to retrieval, generation, or supervisor nodes

### Key Entities

- **RetrievalPlan**: Represents the retrieval strategy for a given query — which domains to search, how many queries to generate, and what parameters to use
- **SearchQuery**: A single search query derived from the original user question, targeting a specific domain or aspect
- **RetrievalResultSet**: The merged, deduplicated, ranked collection of documents from all search queries, with domain attribution and similarity scores preserved
- **ConfidenceAssessment**: An evaluation of retrieval quality based on similarity scores, result count, and domain coverage — determines whether adaptive retry is needed
- **SecuritySignal**: A named policy signal raised by the policy gate (e.g., `account_takeover`, `fraud_suspected`, `pii_disclosure`), with the matched pattern and recommended action
- **EscalationOutcome**: The final routing decision and supporting signals when a query is escalated, persisted on state and emitted as a log event for audit

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Cross-domain queries receive answers that reference documents from 2 or more domains in at least 80% of cases where the query genuinely spans domains
- **SC-002**: Multi-query retrieval improves document recall by at least 30% compared to single-query retrieval for complex, multi-faceted questions
- **SC-003**: End-to-end query processing time remains under 30 seconds, including any adaptive retrieval retries
- **SC-004**: Adaptive retrieval reduces "no relevant documents found" responses by at least 40% compared to single-attempt retrieval
- **SC-005**: Single-domain query performance does not degrade — processing time and answer quality remain within 10% of current baseline
- **SC-006**: Every retrieval attempt (initial and retry) is logged with full parameters and result metadata
- **SC-007**: Account-takeover queries are escalated by the policy gate in 100% of cases that contain the documented signal phrases; retrieval is not invoked for these queries
- **SC-008**: Policy gate adds no more than 50 ms median latency to non-escalated queries (rule-based fast path)
- **SC-009**: Every escalation emits an `escalation_triggered` log event recording the matching signal name and pattern, enabling false-positive review

## Assumptions

- The existing knowledge base document structure (markdown files organized by domain in `docs/knowledge_base/`) is sufficient and does not need restructuring
- The existing vector store and embedding model provide sufficient similarity search quality for multi-query retrieval to be effective
- Cross-domain retrieval is triggered by the supervisor's classification logic — this feature enhances retrieval after routing, not the routing itself
- The existing three-domain structure (billing, technical, account) is the scope for cross-domain retrieval; no new domains are being added
- A maximum of 3 retrieval retries is a reasonable cap for adaptive retrieval before acknowledging a knowledge gap
- The response generator can handle up to 20 document chunks in its context without significant quality degradation
