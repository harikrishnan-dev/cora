"""The refund agent's own product/refund-policy catalog.

Deliberately separate from `CommerceRepository`'s product table: refund
eligibility rules (return window, restocking fee, condition the item must
be in, final-sale exceptions) are a policy concern owned by this agent, not
core commerce data shared with the other specialists.
"""

from __future__ import annotations

DEFAULT_POLICY: dict = {
    "refund_window_days": 30,
    "restocking_fee_pct": 0,
    "condition": "unused, original packaging",
    "final_sale": False,
    "notes": None,
}

# Per-SKU overrides layered on top of DEFAULT_POLICY. Only fields that
# differ from the default need to be listed.
POLICY_OVERRIDES: dict[str, dict] = {
    "NB-JACKET-M": {"condition": "unworn, tags attached"},
    "NB-BOOTS-HIKE": {"condition": "unworn, original box"},
    "NB-HEADLAMP": {
        "refund_window_days": 15,
        "restocking_fee_pct": 15,
        "condition": "unopened, or defective",
    },
    "NB-WATERBOTTLE": {"condition": "unused"},
    "NB-SPEAKER-BT": {
        "refund_window_days": 15,
        "restocking_fee_pct": 15,
        "condition": "unopened, or defective",
    },
    "NB-FLEECE-W": {"condition": "unworn, tags attached"},
    "NB-SANDALS": {
        "refund_window_days": 14,
        "final_sale": True,
        "condition": "unworn",
        "notes": "Clearance item -- refundable only if defective.",
    },
    "NB-MUG-CAMP": {"condition": "unused"},
    "NB-POWERBANK": {
        "refund_window_days": 15,
        "restocking_fee_pct": 15,
        "condition": "unopened, or defective",
    },
    "NB-HAT-SUN": {"condition": "unworn, tags attached"},
}

# Every SKU this store carries is refundable under at least the default
# policy -- POLICY_OVERRIDES only needs to list the SKUs that differ.
KNOWN_PRODUCT_IDS = {
    "NB-TENT-2P",
    "NB-JACKET-M",
    "NB-BOOTS-HIKE",
    "NB-HEADLAMP",
    "NB-COOLER-45",
    "NB-SLEEPBAG",
    "NB-BACKPACK-40",
    "NB-WATERBOTTLE",
    "NB-STOVE-CAMP",
    "NB-SPEAKER-BT",
    "NB-FLEECE-W",
    "NB-SANDALS",
    "NB-KNIFE-MULTI",
    "NB-MUG-CAMP",
    "NB-POWERBANK",
    "NB-HAT-SUN",
}


def get_refund_policy(product_id: str) -> dict | None:
    """Look up the refund policy for a product, layering any SKU-specific
    overrides on top of the store's default policy. Returns None if
    `product_id` isn't a product this store carries."""
    if product_id not in KNOWN_PRODUCT_IDS:
        return None
    policy = {**DEFAULT_POLICY, **POLICY_OVERRIDES.get(product_id, {})}
    return {"product_id": product_id, **policy}
