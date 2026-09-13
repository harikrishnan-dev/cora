from langgraph.graph import END

from cora.agents.graph import (
    route_after_classify,
    route_after_gather,
    route_after_warranty_service,
)
from cora.agents.triage.models import ClassificationDecision, HelpdeskState, InfoGatheringDecision


def _gathered_state(info_complete: bool) -> HelpdeskState:
    return HelpdeskState(info_gathered=InfoGatheringDecision(info_complete=info_complete))


def _classified_state(category: str) -> HelpdeskState:
    return HelpdeskState(
        classification_decision=ClassificationDecision(category=category, urgency="low")
    )


def test_route_after_gather_waits_when_info_incomplete():
    assert route_after_gather(_gathered_state(info_complete=False)) == END


def test_route_after_gather_proceeds_when_info_complete():
    assert route_after_gather(_gathered_state(info_complete=True)) == "classify"


def test_route_after_classify_sends_shipping_delivery_category_to_its_node():
    assert route_after_classify(_classified_state("shipping_delivery")) == "shipping_delivery"


def test_route_after_classify_sends_warranty_service_category_to_its_node():
    assert route_after_classify(_classified_state("warranty_service")) == "warranty_service"


def test_route_after_classify_ends_for_categories_without_a_specialist_node():
    # Every category currently in `ClassificationDecision.category` has a
    # specialist node, so `model_construct` bypasses that Literal to
    # exercise the fallback path directly rather than via a real category.
    state = HelpdeskState(
        classification_decision=ClassificationDecision.model_construct(
            category="unknown", urgency="low"
        )
    )
    assert route_after_classify(state) == END


def test_route_after_warranty_service_hands_off_to_refund_when_not_covered():
    state = HelpdeskState(warranty_handoff_reason="No defect claimed; customer wants a refund.")
    assert route_after_warranty_service(state) == "refund"


def test_route_after_warranty_service_ends_when_resolved():
    state = HelpdeskState(warranty_service_result="Repair ticket #1 logged.")
    assert route_after_warranty_service(state) == END
