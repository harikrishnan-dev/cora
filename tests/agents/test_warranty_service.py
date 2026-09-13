"""Unit tests for the warranty_service agent's own catalog and tools."""

from unittest.mock import MagicMock

from cora.agents.warranty_service.catalog import decide_resolution, get_coverage_policy
from cora.agents.warranty_service.tools import make_warranty_service_tools
from cora.repository.commerce_repository import CommerceRepository


def test_decide_resolution_replaces_cheap_items_regardless_of_category():
    assert decide_resolution("Outdoor Gear", 3900) == "replace"


def test_decide_resolution_repairs_default_category_above_replace_threshold():
    assert decide_resolution("Outdoor Gear", 15000) == "repair"


def test_decide_resolution_refunds_electronics_above_replace_threshold():
    # A genuine, covered defect in a category that isn't practical to
    # service in-house should be routed to Refund, not repaired/replaced.
    assert decide_resolution("Electronics", 15000) == "refund"


def test_get_coverage_policy_excludes_water_damage_for_electronics_unconditionally():
    policy = get_coverage_policy("Electronics")
    assert any("no electronics" in cause for cause in policy["excluded_causes"])


def test_check_return_policy_reuses_refund_catalog():
    fake_commerce = MagicMock(spec=CommerceRepository)
    tools = {t.name: t for t in make_warranty_service_tools(fake_commerce)}

    result = tools["check_return_policy"].invoke({"sku": "NB-SANDALS"})

    assert result["final_sale"] is True


def test_check_return_policy_returns_error_for_unknown_sku():
    fake_commerce = MagicMock(spec=CommerceRepository)
    tools = {t.name: t for t in make_warranty_service_tools(fake_commerce)}

    result = tools["check_return_policy"].invoke({"sku": "NOT-A-REAL-SKU"})

    assert "error" in result
