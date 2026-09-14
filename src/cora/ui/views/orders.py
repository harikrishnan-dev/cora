from __future__ import annotations

import requests
import streamlit as st

from cora.config import get_settings


def _format_amount(amount_cents: int) -> str:
    return f"${amount_cents / 100:,.2f}"


def render() -> None:
    settings = get_settings()

    st.title("Orders")
    st.caption("All orders placed in the store")

    headers = {"X-API-Key": settings.admin_api_key}

    try:
        response = requests.get(f"{settings.api_url}/orders", headers=headers, timeout=30)
        response.raise_for_status()
        orders = response.json()
    except requests.RequestException as exc:
        st.error(f"Error contacting API: {exc}")
        return

    if not orders:
        st.info("No orders yet.")
        return

    st.dataframe(
        [
            {
                "Order": o["order_code"],
                "Customer": o["customer_code"],
                "Date": o["order_date"],
                "Status": o["status"],
                "Total": _format_amount(o["total_cents"]),
                "Carrier": o["carrier"] or "—",
                "Tracking #": o["tracking_number"] or "—",
            }
            for o in orders
        ],
        use_container_width=True,
        hide_index=True,
    )
