# Research: Frontend Chat UI, Agent Observability & Demo Console

**Feature**: `004-frontend-chat-observability`
**Date**: 2026-05-09

## 1. Frontend Framework Selection

**Decision**: Streamlit

**Rationale**: User explicitly specified Streamlit in `design/streamlit-layout.md`. Additionally, Streamlit is the simplest viable choice for a Python-only demo frontend — single file, no build step, no JavaScript toolchain, built-in chat components (`st.chat_message`, `st.chat_input`), and native support for layouts via `st.sidebar`, `st.columns`, `st.tabs`, and `st.expander`.

**Alternatives considered**:
- **Gradio**: Also Python-only with chat components. Less flexible layout control — harder to implement the three-panel design (sidebar + chat + observability). Better for ML model demos than full application UIs.
- **React/Next.js**: Maximum flexibility but requires a separate JS project, build toolchain, and significantly more code. Violates Principle V (Simplicity) for a POC.
- **Panel/Dash**: More complex than Streamlit with steeper learning curves. Overkill for a demo console.

## 2. HTTP Client for Backend Communication

**Decision**: `httpx` (synchronous mode)

**Rationale**: Already a project dependency (used in `tests/` for integration testing via `httpx.AsyncClient`). Supports both sync and async modes. Streamlit's execution model (full script rerun on interaction) works naturally with synchronous HTTP calls. No need for `aiohttp` or `requests`.

**Alternatives considered**:
- **requests**: Would work but adds a new dependency when `httpx` is already available.
- **httpx async**: Would require `asyncio.run()` wrappers in Streamlit context. Unnecessary complexity for sequential request-response flow.

## 3. Chat UI Implementation Pattern

**Decision**: `st.chat_message` + `st.chat_input` with `st.session_state` for history

**Rationale**: Streamlit's native chat components provide:
- User/assistant message bubbles with avatars
- Scrollable message history
- Text input with submit button
- Built-in accessibility

Message history stored in `st.session_state["messages"]` as a list of dicts. Each message includes a `trace` field for assistant messages, containing the full `QueryResponse` data for the observability panel.

**Pattern**:
```python
# Display history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Handle input
if prompt := st.chat_input("Type a message..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Call backend
    response = api_client.send_query(prompt, session_id, ...)
    # Add assistant message with trace
    st.session_state.messages.append({
        "role": "assistant",
        "content": response.response_text,
        "trace": response.dict()
    })
```

## 4. Observability Data Source

**Decision**: Use existing `QueryResponse` metadata — no new backend endpoints needed

**Rationale**: The `QueryResponse` schema already contains all data needed for the five observability tabs:

| Tab | Data Source in QueryResponse |
|---|---|
| Agent Route | `agent`, `routing_rationale`, `metadata.classified_domain`, `metadata.classified_domains` |
| RAG Sources | `citations` (list of `CitationResponse` with content, domain, source, score) |
| Tool Calls | `tool_calls` (list of `ToolCallResult` with tool_name, status, result, error) |
| Guardrail Events | `tool_calls` (block_reason field), `pending_approvals` |
| Raw State JSON | Full `QueryResponse` serialized to JSON |

The `QueryMetadata` object provides timing and count metrics: `total_latency_ms`, `llm_calls`, `retrieval_calls`, `retrieval_attempts`, `documents_retrieved`, `documents_after_dedup`, `retrieval_confidence`.

**Alternatives considered**:
- **Parse structlog JSON output**: Would require log aggregation infrastructure. Logs go to stdout, not queryable from the frontend. Overkill for POC.
- **Add a `/trace/{query_id}` endpoint**: Unnecessary — all trace data is already in the query response. Would duplicate data.

## 5. Guardrails Toggle

**Decision**: Add optional `guardrails_enabled: bool | None` field to `QueryRequest`

**Rationale**: The backend already has `tool_execution_enabled` in `config.py` as a global setting. Adding a per-request override allows the frontend toggle to control guardrails without modifying server config. When `None` (default), the server's global setting applies. When explicitly set, it overrides for that request only.

**Implementation**:
- Frontend: `st.toggle("Guardrails", value=True)` in sidebar
- Request: Include `guardrails_enabled` in POST body
- Backend: Check request field first, fall back to config setting

## 6. Model Selection

**Decision**: Add optional `model_override: str | None` field to `QueryRequest`

**Rationale**: The backend already supports `llm_model` in config. A per-request override lets the demo operator switch models from the UI to compare behavior. Default model options: `gpt-4o-mini` (default), `gpt-4o`, `claude-sonnet-4-6`.

**Implementation**:
- Frontend: `st.selectbox("Model", ["gpt-4o-mini", "gpt-4o", "claude-sonnet-4-6"])` in sidebar
- Request: Include `model_override` in POST body
- Backend: Use override if provided, else use config default

## 7. Customer Selection and Session Management

**Decision**: Sidebar selectbox with preset customer profiles, mapping to `session_id`

**Rationale**: Different "customers" provide different demo contexts. The `session_id` field already exists in `QueryRequest` and is used for rate limiting and conversation context. Selecting a customer sets the session ID, enabling the demo operator to show customer-specific behavior.

**Customer profiles** are hardcoded in `frontend/scenarios.py` (3 profiles for POC).

## 8. Layout Architecture

**Decision**: Three-panel layout using `st.sidebar` + `st.columns`

**Rationale**: `design/streamlit-layout.md` specifies left sidebar, main chat area, and right observability panel. Streamlit supports this via:
- `st.sidebar` for the left panel (native)
- `st.columns([2, 1])` to split the main area into chat (wider) and observability (narrower)
- `st.tabs` inside the right column for the five observability views

This provides a clean three-panel layout without custom CSS or components.

## 9. Streaming Responses

**Decision**: Not implemented in v1

**Rationale**: Streamlit's `st.chat_message` can display streaming text via `st.write_stream()`, but this requires the data source to be a Python generator. The backend currently returns complete responses via REST — implementing streaming would require:
1. Backend: Add SSE or WebSocket endpoint
2. Frontend: Consume streaming response and feed to generator

This is out of scope for POC. A loading spinner (`st.spinner`) provides feedback during processing. Full response renders on completion.

## 10. Session Persistence

**Decision**: `st.session_state` only (no persistence across refreshes)

**Rationale**: The spec explicitly states "single-session mode — there is no persistence of conversations across browser refreshes." Streamlit's `session_state` is tied to the browser tab session. This is the simplest approach and matches the spec assumption.
