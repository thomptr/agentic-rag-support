"""Left sidebar controls: customer, scenario, guardrails, model, reset."""

import streamlit as st

from src.frontend.scenarios import CUSTOMER_PROFILES, SCENARIOS_BY_CATEGORY


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## Demo Controls")

        # Customer selector
        customer_names = {p.id: p.name for p in CUSTOMER_PROFILES}
        customer_ids = [p.id for p in CUSTOMER_PROFILES]
        st.selectbox(
            "Customer",
            options=customer_ids,
            format_func=lambda cid: customer_names[cid],
            key="selected_customer",
        )

        st.markdown("---")

        # Scenario selector grouped by category
        scenario_options = {"— None (freeform) —": None}
        for category, scenarios in SCENARIOS_BY_CATEGORY.items():
            for s in scenarios:
                scenario_options[f"[{category}] {s.title}"] = s

        selected_label = st.selectbox(
            "Preset Scenario",
            options=list(scenario_options.keys()),
        )
        selected_scenario = scenario_options[selected_label]

        if selected_scenario is not None:
            st.caption(selected_scenario.description)
            if st.button("Load Scenario", use_container_width=True):
                st.session_state.pending_query = selected_scenario.query_text
                # Map customer selection to session_id
                st.session_state.session_id = st.session_state.selected_customer
                st.rerun()

        st.markdown("---")

        # Guardrails toggle
        st.toggle(
            "Guardrails",
            value=True,
            key="guardrails_enabled",
            help="Toggle tool execution guardrails on/off",
        )

        # Model selector
        st.selectbox(
            "Model",
            options=["gpt-4o-mini", "gpt-4o", "claude-sonnet-4-6"],
            key="selected_model",
        )

        st.markdown("---")

        # Reset conversation
        if st.button("Reset Conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.last_trace = None
            st.session_state.pending_approvals = []
            st.rerun()
