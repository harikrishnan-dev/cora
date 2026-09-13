"""Uses fake `LLMRepository`/`CommerceRepository`-shaped objects (no real
Anthropic/Postgres calls) so the graph's structure can be tested without an
API key or a database."""

from langchain_core.runnables import RunnableLambda

from cora.agents.graph import build_graph


class _FakeChatModel:
    def with_structured_output(self, schema):
        return RunnableLambda(lambda _: None)

    def invoke(self, *args, **kwargs):
        return None


class _FakeLLMRepository:
    def get_model(self):
        return _FakeChatModel()


class _FakeCommerceRepository:
    """Never called during graph construction -- tools only touch the
    repository when actually invoked, which structural tests don't do."""


def test_build_graph_has_expected_nodes():
    graph = build_graph(_FakeLLMRepository(), _FakeCommerceRepository())
    node_names = set(graph.get_graph().nodes.keys())
    assert {
        "gather_info",
        "classify",
        "refund",
        "shipping_delivery",
        "warranty_service",
    }.issubset(node_names)
