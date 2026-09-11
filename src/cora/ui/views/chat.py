from __future__ import annotations

import uuid

import requests
import streamlit as st

from cora.config import get_settings


def render() -> None:
    settings = get_settings()

    st.title("Chat")
    st.caption("Customer support, powered by LangGraph")

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for role, content in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(content)

    if prompt := st.chat_input("How can we help?"):
        st.session_state.chat_history.append(("user", prompt))
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"), st.spinner("Thinking..."):
            try:
                response = requests.post(
                    f"{settings.api_url}/chat",
                    json={"session_id": st.session_state.session_id, "message": prompt},
                    timeout=60,
                )
                response.raise_for_status()
                reply = response.json()["reply"]
            except requests.RequestException as exc:
                reply = f"Error contacting API: {exc}"
            st.markdown(reply)
        st.session_state.chat_history.append(("assistant", reply))
