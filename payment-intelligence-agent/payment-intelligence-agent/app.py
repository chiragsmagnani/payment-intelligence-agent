"""Streamlit chat interface for the Payment Performance Intelligence Assistant."""

import uuid

import streamlit as st
from dotenv import load_dotenv

from agent.payment_agent import build_agent


load_dotenv()

MAX_MESSAGES_PER_SESSION = 20  # simple abuse/cost guardrail for a public demo

st.set_page_config(
    page_title="Payment Performance Intelligence Assistant",
    page_icon="💳",
    layout="centered",
)

st.title("Payment Performance Intelligence Assistant")
st.caption(
    "Ask questions about approval rates, declines, chargebacks, markets, "
    "channels, and merchant categories."
)


def _get_agent():
    """Create one agent per browser session and retain its conversation memory."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex
    if "agent" not in st.session_state:
        st.session_state.agent = build_agent(st.session_state.session_id)
    return st.session_state.agent


if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hi — I can analyze the payment-performance dataset. "
                "Try asking, “What is our overall approval rate by market?”"
            ),
        }
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask a payment performance question"):
    if len(st.session_state.messages) >= MAX_MESSAGES_PER_SESSION:
        st.warning(
            "This demo session has hit its message limit (a safeguard against "
            "free-tier API abuse on a public demo). Refresh the page to start "
            "a new session."
        )
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing payment performance…"):
            try:
                response = _get_agent().run(prompt)
                answer = response.content or "I could not produce an answer for that question."
            except Exception as exc:
                answer = (
                    "I couldn't answer that right now. "
                    f"Please check the app configuration and try again. ({exc})"
                )
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
