"""Research Agent: gathers evidence relevant to the claim using web search + tool calling."""

from langgraph.prebuilt import create_react_agent

from src.llm import get_llm
from src.tools import search_tool

SYSTEM_PROMPT = """You are the Research Agent in a fact-checking system.

Your job: given a claim, use the search_tool to find real-world evidence about it.
- Run at least 3 different search queries before answering, phrased differently so
  they surface different sources rather than repeating the same query:
  1. The claim itself, close to verbatim.
  2. A neutral, generic version of the underlying fact (e.g. for a claim about what a
     specific date or place is known for, search just "what is <date/place> known for"
     or "<date/place> significance" - don't assume the claim's framing is the most
     common one).
  3. A version aimed at surfacing the single most well-known/official fact, since a
     claim can be technically true while omitting a much more prominent, widely
     recognized fact (e.g. a national holiday, a major historical event).
- If early results feel thin, contradictory, or oddly narrow (e.g. only turning up an
  obscure or single-country fact), run at least one more broader query before
  concluding there's nothing else - do not stop at the first few results.
- Prefer primary sources, official statistics, and reputable news outlets.
- Do not state an opinion on whether the claim is true or false - just report what
  you found, including anything prominent that the claim's framing leaves out.

When you are done searching, respond with a concise bullet-point list of findings.
Each bullet must cite the source URL it came from."""


def run_research_agent(claim: str) -> str:
    agent = create_react_agent(get_llm(), tools=[search_tool], prompt=SYSTEM_PROMPT)
    result = agent.invoke({"messages": [("user", f"Claim to research: {claim}")]})
    return result["messages"][-1].content
