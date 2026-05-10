"""Chat message rendering component."""

import streamlit as st


def render_chat_history(messages: list[dict]) -> None:
    """Render all messages from session state as chat bubbles."""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        avatar = "🧑" if role == "user" else "🤖"
        with st.chat_message(role, avatar=avatar):
            st.markdown(content)
