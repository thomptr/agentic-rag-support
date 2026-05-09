<!--
SYNC IMPACT REPORT
==================
Version change: (none) → 1.0.0 (initial ratification)

New principles:
  - I. RAG-First
  - II. Agentic Autonomy
  - III. Test-First (NON-NEGOTIABLE)
  - IV. Observability
  - V. Simplicity (POC Scope)

New sections:
  - Core Principles
  - Technology Stack
  - Development Workflow
  - Governance

Templates reviewed:
  ✅ .specify/templates/plan-template.md — Constitution Check section present; no updates needed
  ✅ .specify/templates/spec-template.md — Requirements structure compatible; no updates needed
  ✅ .specify/templates/tasks-template.md — Task categories align with principles; no updates needed

Deferred TODOs:
  - None. All placeholders resolved.
-->

# Agentic RAG Support Constitution

## Core Principles

### I. RAG-First

Every agent response MUST be grounded in retrieved context from the knowledge
base. Agents MUST query the retrieval layer before generating any answer.
Responses produced without retrieved evidence — hallucinations — are a critical
failure and MUST be caught by tests.

Retrieval MUST be deterministic enough to be tested: same query → same
candidate documents (within an acceptable similarity threshold).

### II. Agentic Autonomy

The system MUST support multi-step reasoning loops. Agents MUST be able to
decide independently when to retrieve additional context, when to use a tool,
when to escalate to a human, and when to produce a final answer.

Tool use is mandatory for any action beyond a knowledge-base lookup (e.g.,
ticket creation, status queries, external API calls). Agents MUST NOT produce
side effects through natural-language output alone.

### III. Test-First (NON-NEGOTIABLE)

TDD is mandatory: tests are written → user approves → tests confirmed to fail →
implementation begins. The Red-Green-Refactor cycle is strictly enforced.

This applies to all retrieval pipelines, agent reasoning steps, tool
definitions, and API contracts. No implementation task may begin without a
corresponding failing test already in place.

### IV. Observability

Every LLM call MUST record: model, prompt (or prompt hash), input tokens,
output tokens, and wall-clock latency. Every retrieval call MUST record: query,
top-k results with scores, and elapsed time.

Structured logging is required (JSON lines). All agent decisions — retrieve,
tool-call, escalate, respond — MUST emit a structured log event so any run can
be replayed and audited.

### V. Simplicity (POC Scope)

This is a proof of concept. Scope MUST be limited to demonstrating core
RAG + agent capabilities. No premature scaling infrastructure, no production
hardening, and no features that exist only for hypothetical future needs.

Three similar lines of code are preferable to a premature abstraction. If a
simpler approach validates the concept equally well, MUST choose the simpler
approach.

## Technology Stack

The following stack is established for this POC. Deviations require a
constitution amendment.

- **Language**: Python 3.11+
- **AI / LLM**: Claude via the Anthropic SDK (prompt caching enabled)
- **Embeddings / Vector Store**: To be determined during Phase 0 research
  (lightweight store preferred — e.g., ChromaDB or FAISS for POC)
- **Service Layer**: FastAPI (if an HTTP interface is required; otherwise CLI)
- **Testing**: pytest with pytest-asyncio
- **Environment**: `.env` files via `python-dotenv`; secrets never committed

## Development Workflow

- All work happens on feature branches following speckit naming conventions.
- Every PR MUST include a Constitution Check confirming no principle is
  violated (use the plan-template Constitution Check section).
- Tests MUST pass (green) before a PR is merged.
- Complexity violations (principle V) MUST be documented in the plan's
  Complexity Tracking table with justification before implementation begins.
- Commits after each logical task; use speckit git hooks for auto-commit.

## Governance

This constitution supersedes all other practices and informal agreements.
Amendments require: (1) a version bump per semantic versioning, (2) a written
rationale, and (3) updates to all affected templates. CLAUDE.md points to the
current plan for runtime guidance; constitutional changes propagate there.

All PRs and reviews MUST verify compliance with at minimum Principles I, III,
and IV. Principle V violations must be explicitly justified; unjustified
complexity MUST be rejected.

**Version**: 1.0.0 | **Ratified**: 2026-05-08 | **Last Amended**: 2026-05-08
