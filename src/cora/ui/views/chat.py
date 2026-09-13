from __future__ import annotations

import uuid

import requests
import streamlit as st

from cora.config import get_settings


def render() -> None:
    settings = get_settings()

    st.title("Cora")
    st.caption("Your assistant for getting quick, clear answers to your questions")

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "session_token" not in st.session_state:
        st.session_state.session_token = None

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
                    json={
                        "session_id": st.session_state.session_id,
                        "message": prompt,
                        "session_token": st.session_state.session_token,
                    },
                    timeout=60,
                )
                response.raise_for_status()
                body = response.json()
                reply = body["reply"]
                st.session_state.session_token = body["session_token"]
            except requests.RequestException as exc:
                reply = f"Error contacting API: {exc}"
            st.markdown(reply)
        st.session_state.chat_history.append(("assistant", reply))
