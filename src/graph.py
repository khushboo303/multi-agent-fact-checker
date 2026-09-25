"""Orchestration layer: wires the four agents into a single LangGraph StateGraph.

Flow: Research -> Adversarial Verification -> Evidence Synthesis -> Judge

Each node reads whatever it needs from GraphState and returns a partial state
update; LangGraph merges updates into the running state and passes it to the
next node.
"""

from langgraph.graph import END, StateGraph

from src.agents import (
    run_adversarial_agent,
    run_judge_agent,
    run_research_agent,
    run_synthesis_agent,
)
from src.state import GraphState


def _research_node(state: GraphState) -> dict:
    findings = run_research_agent(state["claim"])
    return {
        "research_findings": findings,
        "trace": state.get("trace", []) + ["[Research Agent] gathered initial evidence."],
    }


def _adversarial_node(state: GraphState) -> dict:
    findings = run_adversarial_agent(state["claim"], state["research_findings"])
    return {
        "adversarial_findings": findings,
        "trace": state.get("trace", []) + ["[Adversarial Agent] searched for counter-evidence."],
    }


def _synthesis_node(state: GraphState) -> dict:
    synthesis = run_synthesis_agent(
        state["claim"], state["research_findings"], state["adversarial_findings"]
    )
    return {
        "synthesis": synthesis,
        "trace": state.get("trace", []) + ["[Synthesis Agent] combined both sides into a brief."],
    }


def _judge_node(state: GraphState) -> dict:
    verdict, confidence, reasoning = run_judge_agent(state["claim"], state["synthesis"])
    return {
        "verdict": verdict,
        "confidence": confidence,
        "reasoning": reasoning,
        "trace": state.get("trace", []) + ["[Judge Agent] rendered the final verdict."],
    }


def build_graph():
    """Compile and return the runnable fact-checking graph."""
    graph = StateGraph(GraphState)

    graph.add_node("research", _research_node)
    graph.add_node("adversarial", _adversarial_node)
    graph.add_node("synthesis", _synthesis_node)
    graph.add_node("judge", _judge_node)

    graph.set_entry_point("research")
    graph.add_edge("research", "adversarial")
    graph.add_edge("adversarial", "synthesis")
    graph.add_edge("synthesis", "judge")
    graph.add_edge("judge", END)

    return graph.compile()


def check_claim(claim: str) -> GraphState:
    """Run a single claim through the full multi-agent workflow and return the final state."""
    app = build_graph()
    return app.invoke({"claim": claim, "trace": []})
