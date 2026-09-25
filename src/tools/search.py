"""The one tool every agent can call: a free, no-API-key web search over DuckDuckGo."""

import os

from duckduckgo_search import DDGS
from langchain_core.tools import tool


@tool
def search_tool(query: str) -> str:
    """Search the web for information relevant to a fact-checking claim.

    Args:
        query: The search query (e.g. a claim, or a specific sub-question about it).

    Returns:
        A numbered list of search results, each with a title, source URL, and snippet.
    """
    max_results = int(os.getenv("SEARCH_MAX_RESULTS", "5"))

    try:
        results = list(DDGS().text(query, max_results=max_results))
    except Exception as exc:  # noqa: BLE001 - surface the error to the agent, don't crash the graph
        return f"Search failed for query '{query}': {exc}"

    if not results:
        return f"No search results found for query: {query}"

    formatted = []
    for i, r in enumerate(results, start=1):
        title = r.get("title", "Untitled")
        href = r.get("href", "unknown source")
        body = r.get("body", "")
        formatted.append(f"{i}. {title}\n   Source: {href}\n   {body}")

    return "\n".join(formatted)
