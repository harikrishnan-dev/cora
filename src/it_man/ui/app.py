from __future__ import annotations

import streamlit as st

from it_man.ui.views import chat, pending_requests

st.set_page_config(page_title="it-man", page_icon="🤖", layout="wide")

pages = [
    st.Page(chat.render, title="Chat", icon="💬", url_path="chat", default=True),
    st.Page(
        pending_requests.render,
        title="Pending Requests",
        icon="🕒",
        url_path="pending-requests",
    ),
]

st.navigation(pages).run()
