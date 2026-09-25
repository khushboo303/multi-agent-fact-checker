# Tools

## `search_tool` (`search.py`)

A `@tool`-decorated function (LangChain tool-calling convention) that wraps
[`duckduckgo-search`](https://pypi.org/project/duckduckgo-search/) — free, no API
key required. Given a query string, it returns up to `SEARCH_MAX_RESULTS`
(default 5, set in `.env`) results as a numbered list of `title / source URL / snippet`.

Both the Research Agent and the Adversarial Agent are bound to this same tool; they
just use it with different intent (find supporting evidence vs. find
counter-evidence). This is the *only* tool in the system — kept intentionally
minimal so the project stays easy to read and extend.

**Extending it:** to add a second tool (e.g. a Wikipedia lookup or a dedicated
fact-check-database API), write another `@tool`-decorated function in this folder
and add it to the `tools=[...]` list passed to `create_react_agent(...)` in
`src/agents/research_agent.py` / `adversarial_agent.py`.

**Failure handling:** network errors or empty results are caught and returned to
the agent as a plain string (e.g. `"Search failed for query '...': <error>"`)
rather than raised, so a flaky search never crashes the graph — the agent just
sees the failure and can decide to retry with a different query.
