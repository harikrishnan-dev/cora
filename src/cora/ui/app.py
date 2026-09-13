from __future__ import annotations

import streamlit as st

from cora.ui.views import chat, customers, orders, pending_requests, policies

st.set_page_config(page_title="CORA", page_icon="🤖", layout="wide")

pages = [
    st.Page(chat.render, title="Chat", icon="💬", url_path="chat", default=True),
    st.Page(
        pending_requests.render,
        title="Pending Requests",
        icon="🕒",
        url_path="pending-requests",
    ),
    st.Page(orders.render, title="Orders", icon="📦", url_path="orders"),
    st.Page(policies.render, title="Policies", icon="📋", url_path="policies"),
    st.Page(customers.render, title="Customers", icon="👥", url_path="customers"),
]

st.navigation(pages).run()
