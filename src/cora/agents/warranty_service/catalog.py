"""The warranty/service agent's own coverage and repair-vs-replace policy
catalog.

Deliberately separate from `CommerceRepository`'s product table: `products.
warranty_months` is core commerce data (how long coverage lasts), but what
the warranty actually covers (a manufacturing defect) vs. excludes
(accidental damage, wear and tear, ...), and how a covered defect gets
resolved (repair vs. replace) and priced when it isn't covered, are policy
concerns owned by this agent alone.
"""

from __future__ import annotations

DEFAULT_COVERAGE_POLICY: dict = {
    "covered": "Manufacturing defects -- material or workmanship issues that show up under normal use.",
    "excluded_causes": [
        "accidental damage (drops, impacts, spills)",
        "water damage, unless the product is rated water-resistant or waterproof",
        "normal wear and tear",
        "unauthorized repair or modification",
        "cosmetic damage that doesn't affect how the product works",
        ("damage that occurred in transit (arrived already damaged) -- a carrier "
         "claim, not a warranty claim"),
    ],
}

# Per-category overrides layered on top of DEFAULT_COVERAGE_POLICY.
CATEGORY_COVERAGE_OVERRIDES: dict[str, dict] = {
    "Electronics": {
        "excluded_causes": [
            "accidental damage (drops, impacts, spills)",
            "water damage -- no electronics this store carries are water-resistant",
            "normal wear and tear",
            "unauthorized repair or modification",
            "cosmetic damage that doesn't affect how the product works",
            ("damage that occurred in transit (arrived already damaged) -- a carrier "
             "claim, not a warranty claim"),
        ],
    },
}


def get_coverage_policy(category: str | None) -> dict:
    """The warranty coverage policy for a product category: what's covered
    vs. what causes are excluded, layering any category-specific overrides
    on top of the store's default policy."""
    return {**DEFAULT_COVERAGE_POLICY, **CATEGORY_COVERAGE_OVERRIDES.get(category, {})}


DEFAULT_RESOLUTION_POLICY: dict = {
    "resolution": "repair",
    "replace_below_cents": 6000,
    "repair_cost_pct": 35,
}

# Per-category overrides layered on top of DEFAULT_RESOLUTION_POLICY. Only
# fields that differ from the default need to be listed.
CATEGORY_RESOLUTION_OVERRIDES: dict[str, dict] = {
    # Small electronics aren't practical to repair or swap in-house -- a
    # genuine, covered defect here goes to Refund instead (see
    # ForwardToRefund in warranty_service/models.py), and an out-of-warranty
    # repair is quoted higher since it's really a discounted replacement.
    "Electronics": {"resolution": "refund", "repair_cost_pct": 60},
}


def get_service_policy(category: str | None) -> dict:
    """The repair/replace/refund policy for a product category, layering
    any category-specific overrides on top of the store's default policy."""
    return {**DEFAULT_RESOLUTION_POLICY, **CATEGORY_RESOLUTION_OVERRIDES.get(category, {})}


def decide_resolution(category: str | None, price_cents: int) -> str:
    """How a genuine, covered defect should be resolved: "repair",
    "replace", or "refund" (the category isn't practical to service
    in-house, so send the customer to Refund instead).

    Cheap items are always replaced outright -- below `replace_below_cents`,
    a repair (or a refund) costs more in overhead than the item is worth --
    regardless of what the category's default resolution is.
    """
    policy = get_service_policy(category)
    if price_cents < policy["replace_below_cents"]:
        return "replace"
    return policy["resolution"]


def estimate_repair_cost_cents(category: str | None, price_cents: int) -> int:
    """Quote for a paid, out-of-warranty repair: a percentage of retail
    price set by the category's policy."""
    policy = get_service_policy(category)
    return round(price_cents * policy["repair_cost_pct"] / 100)
