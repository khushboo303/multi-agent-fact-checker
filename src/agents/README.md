# Agents

Four agents, each a focused unit with one job. `research` and `adversarial` are
LangGraph [`create_react_agent`](https://langchain-ai.github.io/langgraph/reference/prebuilt/)
tool-calling agents (they can call `search_tool` in a loop). `synthesis` and `judge`
are plain single-shot LLM calls — they only reason over text they're given, so they
don't need tools.

| File | Role | Tools | Input | Output |
|---|---|---|---|---|
| `research_agent.py` | Gather evidence *for* the claim | `search_tool` | claim | bullet list of findings + sources |
| `adversarial_agent.py` | Actively try to disprove the claim / poke holes in the research | `search_tool` | claim + research findings | bullet list of counter-evidence + concerns |
| `synthesis_agent.py` | Merge both sides into one balanced, neutral brief | none | claim + both findings | evidence brief (no verdict) |
| `judge_agent.py` | Weigh the evidence brief and decide | none | claim + evidence brief | `VERDICT` / `CONFIDENCE` / `REASONING` |

## Research Agent's search strategy

`research_agent.py`'s prompt requires at least 3 differently-phrased queries
per claim (the claim itself, a neutral/generic rephrasing, and one aimed at
surfacing the single most prominent/official fact the claim's framing might
omit), plus a rule to run a further, broader query if early results look thin
or oddly narrow. This exists because a small local model doing a couple of
narrow searches will sometimes miss a much more prominent fact entirely (e.g.
missing a well-known national holiday because the first search only surfaced
an obscure one) — widening the query strategy reduces, but does not
eliminate, that failure mode. See the "Known limitation" section in the root
README for what this can and can't fix.

## Why a separate adversarial step?

A single research agent tends to confirm whatever it searches for first (the
evidence it finds shapes the queries it runs next). Giving a second agent the
explicit, adversarial job of trying to disprove the claim — and grading the first
agent's sources while it's at it — is what makes this a *verification* system
rather than a single-pass search-and-summarize pipeline.

## Judge output format

The judge is instructed to always reply in a fixed three-line format
(`VERDICT: / CONFIDENCE: / REASONING:`), parsed with a small regex in
`judge_agent.py`. This is deliberately simpler than a tool/schema-based structured
output call — local models via Ollama have inconsistent support for strict JSON
mode, and a plain-text format with a forgiving parser is more robust across models.
If a field is missing from the model's response, the parser falls back to safe
defaults (`UNVERIFIABLE` / `N/A`) instead of raising.
