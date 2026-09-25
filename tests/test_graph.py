"""Smoke test for the orchestration graph's structure (no live LLM/network calls)."""

from src.graph import build_graph


def test_graph_compiles():
    app = build_graph()
    node_names = set(app.get_graph().nodes.keys())
    assert {"research", "adversarial", "synthesis", "judge"}.issubset(node_names)
