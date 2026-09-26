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

# Below this, the Judge's own verdict isn't trusted enough to stop - the graph
# loops back to Research instead of ending. Capped at one retry (2 total attempts)
# so a claim that's genuinely hard to verify can't loop forever.
CONFIDENCE_THRESHOLD = 50
MAX_ATTEMPTS = 2


def _research_node(state: GraphState) -> dict:
    attempts = state.get("attempts", 0)
    retry_context = None
    temperature = 0.0

    if attempts > 0:
        # Looping back after a low-confidence verdict: tell Research what the
        # previous pass concluded and why it wasn't convincing, and raise the
        # temperature slightly so it's less likely to run the exact same
        # searches and land on the exact same findings again.
        temperature = 0.4
        retry_context = (
            f"NOTE: this is a retry. A previous pass on this claim reached "
            f"{state.get('confidence', '?')}% confidence, below the "
            f"{CONFIDENCE_THRESHOLD}% bar this system requires, with this "
            f"reasoning: \"{state.get('reasoning', '')}\"\n"
            "Don't just repeat the same searches - try different angles or "
            "more specific sub-questions that might close that gap."
        )

    findings = run_research_agent(state["claim"], retry_context=retry_context, temperature=temperature)
    label = "gathered initial evidence." if attempts == 0 else f"retried search (attempt {attempts + 1})."
    return {
        "research_findings": findings,
        "trace": state.get("trace", []) + [f"[Research Agent] {label}"],
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


def _prepare_retry_node(state: GraphState) -> dict:
    """A conditional edge can only pick the next node - it can't update state
    itself - so this plain node does the actual attempts += 1 before looping
    back to research."""
    attempts = state.get("attempts", 0) + 1
    return {
        "attempts": attempts,
        "trace": state.get("trace", [])
        + [
            f"[Orchestrator] confidence {state.get('confidence')}% is below "
            f"{CONFIDENCE_THRESHOLD}% - retrying (attempt {attempts + 1})."
        ],
    }


def _route_after_judge(state: GraphState) -> str:
    """Decides whether the graph is actually done, or should loop back to
    research for another attempt - the one place this graph makes a real,
    data-dependent decision instead of just following a fixed sequence."""
    try:
        confidence = int(state.get("confidence", "0"))
    except (TypeError, ValueError):
        # Judge didn't return a parseable number - don't retry on that alone.
        confidence = 100

    attempts = state.get("attempts", 0)
    if confidence < CONFIDENCE_THRESHOLD and attempts + 1 < MAX_ATTEMPTS:
        return "retry"
    return "end"


def build_graph():
    """Compile and return the runnable fact-checking graph."""
    graph = StateGraph(GraphState)

    graph.add_node("research", _research_node)
    graph.add_node("adversarial", _adversarial_node)
    graph.add_node("synthesis", _synthesis_node)
    graph.add_node("judge", _judge_node)
    graph.add_node("prepare_retry", _prepare_retry_node)

    graph.set_entry_point("research")
    graph.add_edge("research", "adversarial")
    graph.add_edge("adversarial", "synthesis")
    graph.add_edge("synthesis", "judge")
    graph.add_conditional_edges("judge", _route_after_judge, {"retry": "prepare_retry", "end": END})
    graph.add_edge("prepare_retry", "research")

    return graph.compile()


def check_claim(claim: str) -> GraphState:
    """Run a single claim through the full multi-agent workflow and return the final state."""
    app = build_graph()
    return app.invoke({"claim": claim, "trace": []})
