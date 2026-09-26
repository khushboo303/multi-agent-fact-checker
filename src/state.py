"""Shared state that flows through every node of the LangGraph orchestration graph."""

from typing import List, TypedDict


class GraphState(TypedDict, total=False):
    # Input
    claim: str

    # Research Agent output: raw findings supporting/discussing the claim
    research_findings: str

    # Adversarial Agent output: counter-evidence and challenges to the research findings
    adversarial_findings: str

    # Evidence Synthesizer output: a balanced write-up combining both sides
    synthesis: str

    # Judge output
    verdict: str
    confidence: str
    reasoning: str

    # Human-readable log of what happened at each step, shown in the CLI output
    trace: List[str]

    # How many times Research has run for this claim. 0 on the first pass;
    # incremented when the Judge's confidence is too low and the graph loops
    # back - see _route_after_judge() in graph.py.
    attempts: int
