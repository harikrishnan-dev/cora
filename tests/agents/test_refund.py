"""Unit tests for the refund agent's own catalog and tools.

Deliberately doesn't import cora.agents.refund.agent: it depends on
cora.agents.triage.models.HelpdeskState, which is under active development
and not yet import-safe (see QueryDetails)."""

from unittest.mock import MagicMock

from cora.agents.refund.catalog import get_refund_policy
from cora.agents.refund.tools import make_refund_tools
from cora.repository.commerce_repository import CommerceRepository


def test_get_refund_policy_applies_sku_override_on_top_of_default():
    policy = get_refund_policy("NB-SANDALS")
    assert policy["final_sale"] is True
    assert policy["refund_window_days"] == 14  # overridden
    assert policy["restocking_fee_pct"] == 0  # inherited from default


def test_get_refund_policy_falls_back_to_default_for_unlisted_sku():
    policy = get_refund_policy("NB-TENT-2P")
    assert policy["refund_window_days"] == 30
    assert policy["final_sale"] is False


def test_get_refund_policy_returns_none_for_unknown_product():
    assert get_refund_policy("NOT-A-REAL-SKU") is None


def test_is_already_refunded_or_not_reports_pending_and_approved():
    fake_commerce = MagicMock(spec=CommerceRepository)
    fake_commerce.get_refund_requests_for_order.return_value = [
        {"id": 1, "status": "pending"},
    ]
    _, is_already_refunded_or_not, _ = make_refund_tools(fake_commerce)

    result = is_already_refunded_or_not.invoke({"order_code": "ORD-1"})

    assert result["has_pending_request"] is True
    assert result["already_refunded"] is False


def test_is_already_refunded_or_not_true_when_approved():
    fake_commerce = MagicMock(spec=CommerceRepository)
    fake_commerce.get_refund_requests_for_order.return_value = [
        {"id": 1, "status": "approved"},
    ]
    _, is_already_refunded_or_not, _ = make_refund_tools(fake_commerce)

    result = is_already_refunded_or_not.invoke({"order_code": "ORD-1"})

    assert result["already_refunded"] is True


def test_initiate_refund_delegates_to_commerce_repository():
    fake_commerce = MagicMock(spec=CommerceRepository)
    fake_commerce.create_refund_request.return_value = {"id": 1, "status": "pending"}
    _, _, initiate_refund = make_refund_tools(fake_commerce)

    result = initiate_refund.invoke(
        {"order_code": "ORD-1", "amount_cents": 1200, "reason": "wrong size"}
    )

    fake_commerce.create_refund_request.assert_called_once_with("ORD-1", 1200, "wrong size")
    assert result["status"] == "pending"
