from __future__ import annotations

import requests
import streamlit as st

from cora.config import get_settings


def render() -> None:
    settings = get_settings()

    st.title("Customers")
    st.caption("All registered customers")

    headers = {"X-API-Key": settings.admin_api_key}

    try:
        response = requests.get(f"{settings.api_url}/customers", headers=headers, timeout=30)
        response.raise_for_status()
        customers = response.json()
    except requests.RequestException as exc:
        st.error(f"Error contacting API: {exc}")
        return

    if not customers:
        st.info("No customers yet.")
        return

    st.dataframe(
        [
            {
                "Customer": c["customer_code"],
                "Name": c["full_name"],
                "Email": c["email"],
                "Phone": c["phone"] or "—",
            }
            for c in customers
        ],
        use_container_width=True,
        hide_index=True,
    )
