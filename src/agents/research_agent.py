"""Research Agent: gathers evidence relevant to the claim using web search + tool calling."""

from langgraph.prebuilt import create_react_agent

from src.llm import get_llm
from src.tools import search_tool

SYSTEM_PROMPT = """You are the Research Agent in a fact-checking system.

Your job: given a claim, use the search_tool to find real-world evidence about it.
- Run at least 2 different search queries (e.g. the claim itself, and a more specific
  sub-question about it) before answering.
- Prefer primary sources, official statistics, and reputable news outlets.
- Do not state an opinion on whether the claim is true or false - just report what
  you found.

When you are done searching, respond with a concise bullet-point list of findings.
Each bullet must cite the source URL it came from."""


def run_research_agent(claim: str) -> str:
    agent = create_react_agent(get_llm(), tools=[search_tool], prompt=SYSTEM_PROMPT)
    result = agent.invoke({"messages": [("user", f"Claim to research: {claim}")]})
    return result["messages"][-1].content
