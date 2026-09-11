from langgraph.graph import END

from cora.agents.graph import route_after_classify, route_after_gather
from cora.agents.state import HelpdeskState


def _state(**overrides) -> HelpdeskState:
    return HelpdeskState(**overrides)


def test_route_after_gather_waits_when_info_incomplete():
    assert route_after_gather(_state(info_complete=False)) == END


def test_route_after_gather_proceeds_when_info_complete():
    assert route_after_gather(_state(info_complete=True)) == "classify"


def test_route_after_classify_maps_every_category_to_a_specialist():
    expected = {
        "refund": "refund",
        "warranty_service": "warranty_service",
        "shipping_delivery": "shipping_delivery",
        "order_change": "order_changes",
    }
    for category, specialist in expected.items():
        assert route_after_classify(_state(category=category)) == specialist
