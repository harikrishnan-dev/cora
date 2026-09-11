from langgraph.graph import END

from cora.agents.graph import route_after_classify, route_after_gather
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


def test_route_after_classify_sends_refund_category_to_refund_node():
    assert route_after_classify(_classified_state("refund")) == "refund"


def test_route_after_classify_ends_for_categories_without_a_specialist_node():
    assert route_after_classify(_classified_state("warranty_service")) == END
