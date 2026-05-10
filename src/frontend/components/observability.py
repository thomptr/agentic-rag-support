"""Observability panel: 5 tabs showing full agent execution trace."""

import streamlit as st


def render_observability(trace: dict | None) -> None:
    st.markdown("### Agent Observability")

    if trace is None:
        st.info("Send a message to see the agent trace here.")
        return

    metadata = trace.get("metadata", {})

    # Metrics summary row
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Latency (ms)", f"{metadata.get('total_latency_ms', 0):.0f}")
    col2.metric("LLM Calls", metadata.get("llm_calls", 0))
    col3.metric("Retrieval Calls", metadata.get("retrieval_calls", 0))
    col4.metric("Docs Retrieved", metadata.get("documents_retrieved", 0))
    confidence = metadata.get("retrieval_confidence")
    col5.metric("Confidence", f"{confidence:.2f}" if confidence is not None else "—")

    # Five observability tabs
    tab_route, tab_rag, tab_tools, tab_guardrails, tab_raw = st.tabs(
        ["Agent Route", "RAG Sources", "Tool Calls", "Guardrail Events", "Raw State JSON"]
    )

    with tab_route:
        _render_agent_route(trace, metadata)

    with tab_rag:
        _render_rag_sources(trace)

    with tab_tools:
        _render_tool_calls(trace)

    with tab_guardrails:
        _render_guardrail_events(trace)

    with tab_raw:
        st.json(trace)


def _render_agent_route(trace: dict, metadata: dict) -> None:
    agent = trace.get("agent", "unknown")
    rationale = trace.get("routing_rationale")
    domains = metadata.get("classified_domains", [])
    confidence = metadata.get("retrieval_confidence")

    with st.expander("Routing Details", expanded=True):
        st.markdown(f"**Routed to**: `{agent}`")
        if domains:
            st.markdown(f"**Classified domain(s)**: {', '.join(domains)}")
        if rationale:
            st.markdown(f"**Rationale**: {rationale}")
        if confidence is not None:
            st.markdown(f"**Retrieval confidence**: {confidence:.2f}")


def _render_rag_sources(trace: dict) -> None:
    citations = trace.get("citations", [])
    if not citations:
        st.info("No RAG sources retrieved for this query.")
        return

    for i, citation in enumerate(citations, 1):
        score = citation.get("score", 0.0)
        source = citation.get("source") or citation.get("source_file", "")
        domain = citation.get("domain", "")
        content = citation.get("content") or citation.get("chunk_text", "")
        title = citation.get("title", f"Document {i}")

        label = f"**{title or source}** — score: {score:.2f} | domain: {domain}"
        with st.expander(label):
            st.markdown(f"**Source**: `{source}`")
            st.progress(min(score, 1.0), text=f"Relevance: {score:.2f}")
            st.markdown(content)


def _render_tool_calls(trace: dict) -> None:
    tool_calls = trace.get("tool_calls", [])
    if not tool_calls:
        st.info("No tool calls were made for this query.")
        return

    for call in tool_calls:
        tool_name = call.get("tool_name", "unknown")
        status = call.get("status", "unknown")
        result = call.get("result")
        error = call.get("error")
        block_reason = call.get("block_reason")

        badge = {"success": "✅", "blocked": "🚫", "pending_approval": "⏳", "error": "❌"}.get(
            status, "❓"
        )
        with st.expander(f"{badge} **{tool_name}** — {status}"):
            if result:
                st.markdown("**Result:**")
                st.json(result)
            if error:
                st.warning(f"Error: {error}")
            if block_reason:
                st.error(f"Blocked: {block_reason}")


def _render_guardrail_events(trace: dict) -> None:
    tool_calls = trace.get("tool_calls", [])
    pending = trace.get("pending_approvals", [])

    blocked = [c for c in tool_calls if c.get("status") == "blocked"]

    if not blocked and not pending:
        st.success("No guardrail events — all tool calls proceeded normally.")
        return

    if blocked:
        st.markdown("**Blocked tool calls:**")
        for call in blocked:
            with st.expander(f"🚫 {call.get('tool_name')} blocked"):
                st.markdown(f"**Reason**: {call.get('block_reason', 'Unknown')}")
                if call.get("error"):
                    st.markdown(f"**Detail**: {call['error']}")

    if pending:
        st.markdown("**Pending approvals:**")
        for item in pending:
            with st.expander(f"⏳ {item.get('tool_name')} awaiting approval"):
                st.markdown(f"**ID**: `{item.get('id')}`")
                st.markdown(f"**Status**: {item.get('status')}")
                st.markdown("**Parameters:**")
                st.json(item.get("parameters", {}))
