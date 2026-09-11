from __future__ import annotations

import requests
import streamlit as st

from cora.config import get_settings


def _format_amount(amount_cents: int) -> str:
    return f"${amount_cents / 100:,.2f}"


def render() -> None:
    settings = get_settings()

    st.title("Pending Requests")
    st.caption("Refund requests awaiting human approval")

    try:
        response = requests.get(f"{settings.api_url}/refund-requests", params={"status": "pending"}, timeout=30)
        response.raise_for_status()
        requests_data = response.json()
    except requests.RequestException as exc:
        st.error(f"Error contacting API: {exc}")
        return

    if not requests_data:
        st.info("No pending requests.")
        return

    for item in requests_data:
        with st.container(border=True):
            st.markdown(
                f"**Order `{item['order_code']}`** — {_format_amount(item['amount_cents'])}"
            )
            st.caption(item["reason"] or "No reason given")
            st.caption(f"Requested at {item['requested_at']}")

            approve_col, reject_col = st.columns(2)
            if approve_col.button("Approve", key=f"approve-{item['id']}", type="primary"):
                requests.post(
                    f"{settings.api_url}/refund-requests/{item['id']}/approve", timeout=30
                )
                st.rerun()
            if reject_col.button("Reject", key=f"reject-{item['id']}"):
                requests.post(
                    f"{settings.api_url}/refund-requests/{item['id']}/reject", timeout=30
                )
                st.rerun()
