"""Tests for the orchestration graph's structure and retry logic (no live LLM/network calls)."""

from unittest.mock import patch

from src import graph as graph_module
from src.graph import (
    CONFIDENCE_THRESHOLD,
    MAX_ATTEMPTS,
    _prepare_retry_node,
    _route_after_judge,
    build_graph,
)


def test_graph_compiles():
    app = build_graph()
    node_names = set(app.get_graph().nodes.keys())
    assert {"research", "adversarial", "synthesis", "judge", "prepare_retry"}.issubset(
        node_names
    )


def test_route_after_judge_retries_on_low_confidence():
    state = {"confidence": str(CONFIDENCE_THRESHOLD - 1), "attempts": 0}
    assert _route_after_judge(state) == "retry"


def test_route_after_judge_stops_once_max_attempts_reached():
    state = {"confidence": str(CONFIDENCE_THRESHOLD - 1), "attempts": MAX_ATTEMPTS - 1}
    assert _route_after_judge(state) == "end"


def test_route_after_judge_ends_on_high_confidence():
    state = {"confidence": "90", "attempts": 0}
    assert _route_after_judge(state) == "end"


def test_route_after_judge_does_not_retry_on_unparseable_confidence():
    state = {"confidence": "N/A", "attempts": 0}
    assert _route_after_judge(state) == "end"


def test_prepare_retry_node_increments_attempts_and_logs():
    state = {"confidence": "30", "attempts": 0, "trace": []}
    update = _prepare_retry_node(state)
    assert update["attempts"] == 1
    assert any("retrying" in line for line in update["trace"])


def test_graph_loops_back_to_research_on_low_confidence():
    """End-to-end check (agents mocked out) that a low first-pass confidence
    actually causes the compiled graph to run Research/Judge twice, and that
    the second pass's result is what comes out the other end."""
    judge_calls = {"count": 0}

    def fake_judge(claim, synthesis):
        judge_calls["count"] += 1
        if judge_calls["count"] == 1:
            return ("FALSE", "30", "weak evidence on first pass")
        return ("TRUE", "90", "strong evidence on retry")

    with patch.object(graph_module, "run_research_agent", lambda *a, **k: "findings"), \
         patch.object(graph_module, "run_adversarial_agent", lambda *a, **k: "counter-findings"), \
         patch.object(graph_module, "run_synthesis_agent", lambda *a, **k: "brief"), \
         patch.object(graph_module, "run_judge_agent", fake_judge):
        app = build_graph()
        result = app.invoke({"claim": "test claim", "trace": []})

    assert judge_calls["count"] == 2
    assert result["attempts"] == 1
    assert result["verdict"] == "TRUE"
    assert result["confidence"] == "90"
