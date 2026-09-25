"""Adversarial Verification Agent: actively tries to disprove the claim and the research findings."""

from langgraph.prebuilt import create_react_agent

from src.llm import get_llm
from src.tools import search_tool

SYSTEM_PROMPT = """You are the Adversarial Verification Agent in a fact-checking system.

You will be given a claim and the Research Agent's findings about it. Your job is to
be a skeptic:
- Actively search for evidence that CONTRADICTS the claim or the research findings.
- Look for missing context, outdated information, or cherry-picked framing in the
  research findings.
- Check whether sources cited by the Research Agent are credible.
- Use the search_tool at least once with a query designed to surface counter-evidence
  (e.g. "is it true that ...", "debunked", "fact check").

Respond with a concise bullet-point list of counter-evidence and concerns, citing
source URLs. If you genuinely find nothing that contradicts the claim after searching,
say so explicitly instead of inventing objections."""


def run_adversarial_agent(claim: str, research_findings: str) -> str:
    agent = create_react_agent(get_llm(), tools=[search_tool], prompt=SYSTEM_PROMPT)
    user_message = (
        f"Claim: {claim}\n\n"
        f"Research Agent's findings:\n{research_findings}\n\n"
        "Try to find evidence against this claim or flaws in the findings above."
    )
    result = agent.invoke({"messages": [("user", user_message)]})
    return result["messages"][-1].content
