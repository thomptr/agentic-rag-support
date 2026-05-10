"""Main Streamlit application for the Agentic RAG Support demo."""

import uuid

import httpx
import streamlit as st

from src.frontend import api_client
from src.frontend.components.chat import render_chat_history
from src.frontend.components.observability import render_observability
from src.frontend.components.sidebar import render_sidebar


def _init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "last_trace" not in st.session_state:
        st.session_state.last_trace = None
    if "pending_approvals" not in st.session_state:
        st.session_state.pending_approvals = []
    if "guardrails_enabled" not in st.session_state:
        st.session_state.guardrails_enabled = True
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "gpt-4o-mini"
    if "selected_customer" not in st.session_state:
        st.session_state.selected_customer = "cust-001"
    if "pending_query" not in st.session_state:
        st.session_state.pending_query = None


def _submit_query(query_text: str) -> None:
    st.session_state.messages.append({"role": "user", "content": query_text})

    with st.spinner("Thinking..."):
        try:
            result = api_client.send_query(
                query_text=query_text,
                session_id=st.session_state.session_id,
                guardrails_enabled=st.session_state.guardrails_enabled,
                model_override=st.session_state.selected_model,
            )
            response_text = result.get("response_text", "")
            st.session_state.messages.append(
                {"role": "assistant", "content": response_text, "trace": result}
            )
            st.session_state.last_trace = result
            st.session_state.pending_approvals = result.get("pending_approvals", [])
        except httpx.ConnectError:
            st.error(
                "Could not connect to the backend. "
                "Make sure the FastAPI server is running on port 8000: "
                "`uvicorn src.api.main:app --reload --port 8000`"
            )
        except httpx.TimeoutException:
            st.error(
                "The request timed out after 30 seconds. "
                "The backend may be busy — please try again."
            )
        except httpx.HTTPStatusError as exc:
            st.error(f"Backend returned an error ({exc.response.status_code}): {exc.response.text}")


def _render_welcome() -> None:
    st.markdown("## Welcome to the Agentic RAG Support Demo")
    st.markdown(
        "Ask a support question below, or choose a preset scenario from the sidebar. "
        "After each response, the observability panel shows the full agent trace."
    )
    st.markdown("**Example questions:**")
    examples = [
        "How do I update my billing information?",
        "What are the API rate limits for the pro plan?",
        "How do I reset my password?",
    ]
    cols = st.columns(len(examples))
    for col, example in zip(cols, examples):
        if col.button(example, use_container_width=True):
            st.session_state.pending_query = example
            st.rerun()


def _render_approval_management() -> None:
    approvals = st.session_state.pending_approvals
    if not approvals:
        return

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"### Pending Approvals ({len(approvals)})")
    for approval in approvals:
        with st.sidebar.expander(f"**{approval['tool_name']}** — review required"):
            st.json(approval.get("parameters", {}))
            col1, col2 = st.columns(2)
            if col1.button("Approve", key=f"approve_{approval['id']}"):
                try:
                    api_client.approve_action(approval["id"])
                    st.session_state.pending_approvals = [
                        a for a in st.session_state.pending_approvals if a["id"] != approval["id"]
                    ]
                    st.success("Approved.")
                    st.rerun()
                except httpx.HTTPStatusError as exc:
                    st.error(f"Approval failed: {exc.response.text}")
            if col2.button("Reject", key=f"reject_{approval['id']}"):
                try:
                    api_client.reject_action(approval["id"])
                    st.session_state.pending_approvals = [
                        a for a in st.session_state.pending_approvals if a["id"] != approval["id"]
                    ]
                    st.warning("Rejected.")
                    st.rerun()
                except httpx.HTTPStatusError as exc:
                    st.error(f"Rejection failed: {exc.response.text}")


def main() -> None:
    st.set_page_config(
        page_title="Agentic RAG Support Demo",
        page_icon="🤖",
        layout="wide",
    )

    _init_session_state()

    # Sidebar: controls + approval management
    render_sidebar()
    _render_approval_management()

    # Two-column layout: chat (left) + observability (right)
    chat_col, obs_col = st.columns([2, 1])

    with chat_col:
        st.title("Agentic RAG Support Demo")

        if not st.session_state.messages:
            _render_welcome()
        else:
            render_chat_history(st.session_state.messages)

        # Handle pre-filled query from sidebar scenario selection
        if st.session_state.pending_query:
            query = st.session_state.pending_query
            st.session_state.pending_query = None
            _submit_query(query)
            st.rerun()

        if prompt := st.chat_input("Type a support question..."):
            _submit_query(prompt)
            st.rerun()

    with obs_col:
        render_observability(st.session_state.last_trace)


if __name__ == "__main__":
    main()
