from __future__ import annotations

import requests
import streamlit as st

from cora.config import get_settings


def _format_amount(amount_cents: int) -> str:
    return f"${amount_cents / 100:,.2f}"


def render() -> None:
    settings = get_settings()

    st.title("Product Policies")
    st.caption("Warranty coverage and repair/replace policy for a product")

    headers = {"X-API-Key": settings.admin_api_key}

    try:
        response = requests.get(f"{settings.api_url}/products", headers=headers, timeout=30)
        response.raise_for_status()
        products = response.json()
    except requests.RequestException as exc:
        st.error(f"Error contacting API: {exc}")
        return

    if not products:
        st.info("No products yet.")
        return

    options = {f"{p['name']} ({p['sku']})": p["sku"] for p in products}
    label = st.selectbox("Product", list(options.keys()))
    sku = options[label]

    try:
        response = requests.get(
            f"{settings.api_url}/products/{sku}/policy", headers=headers, timeout=30
        )
        response.raise_for_status()
        policy = response.json()
    except requests.RequestException as exc:
        st.error(f"Error contacting API: {exc}")
        return

    col1, col2 = st.columns(2)
    col1.metric("Price", _format_amount(policy["price_cents"]))
    col2.metric("Warranty", f"{policy['warranty_months']} months")
    st.caption(f"Category: {policy['category'] or 'Uncategorized'}")

    st.subheader("Coverage")
    coverage = policy["coverage"]
    st.markdown(f"**Covered:** {coverage['covered']}")
    st.markdown("**Excluded causes:**")
    for cause in coverage["excluded_causes"]:
        st.markdown(f"- {cause}")

    st.subheader("Resolution")
    service = policy["service"]
    st.markdown(f"**Default resolution:** {service['resolution']}")
    st.markdown(f"**Replaced outright below:** {_format_amount(service['replace_below_cents'])}")
    st.markdown(f"**Out-of-warranty repair cost:** {service['repair_cost_pct']}% of retail price")
