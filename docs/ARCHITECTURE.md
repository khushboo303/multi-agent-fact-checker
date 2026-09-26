# Architecture

## Orchestration layer

`src/graph.py` is the orchestration layer: it defines the shared `GraphState`
that flows between agents, wraps each agent as a graph node, and wires the
nodes into a [LangGraph](https://langchain-ai.github.io/langgraph/)
`StateGraph` with one real, data-dependent decision in it — whether to accept
the Judge's verdict or loop back and try again:

```
        ┌──────────┐     ┌─────────────┐     ┌───────────┐     ┌───────┐
 claim →│ Research │────▶│ Adversarial │────▶│ Synthesis │────▶│ Judge │
        │  Agent   │     │   Agent     │     │   Agent   │     │ Agent │
        └──────────┘     └─────────────┘     └───────────┘     └───┬───┘
             │                   │                       confidence≥50%? │
             └────── search_tool (DuckDuckGo) ──────┘                    │
                              ▲                                          │
                              │            confidence<50% and            ▼
                    ┌──────────────────┐   attempts<2              verdict
                    │  prepare_retry    │◀──────────────────────────────┘
                    └──────────────────┘
```

Each node is a plain Python function `(GraphState) -> dict` that reads whatever
fields it needs off the state and returns a partial update. LangGraph merges
that update into the running state before calling the next node.

**The Research → Adversarial → Synthesis → Judge portion is still strictly
sequential**, for the same reason as before: each node genuinely depends on
the previous one's output, so there's nothing to run in parallel there. What's
no longer true is that the *whole graph* is a single fixed path — see below.

### The retry loop: a real conditional edge

`graph.add_conditional_edges("judge", _route_after_judge, {"retry": "prepare_retry", "end": END})`
is the one place this graph makes a decision instead of just following a fixed
sequence. `_route_after_judge()` parses the Judge's `confidence` and checks it
against `CONFIDENCE_THRESHOLD` (50): if it's below that *and* the claim hasn't
already been retried (`MAX_ATTEMPTS = 2` total attempts), the graph routes to
`prepare_retry` (which increments `state["attempts"]` and logs why) and then
back to `research` — a real cycle, not a straight line. Otherwise it routes to
`END`.

On a retry, `_research_node` passes the previous attempt's confidence and
reasoning back into the Research Agent's prompt (telling it not to just repeat
the same searches) and raises its temperature from 0.0 to 0.4, so a second pass
is more likely to actually differ from the first rather than reproduce the
same result.

**Important caveat:** this only fires when the Judge itself reports low
confidence. A model that's *confidently wrong* — which is what happened with
some of this project's known misses (see the root README) — won't trigger a
retry, because nothing about the pipeline can tell "confident and correct"
apart from "confident and wrong" without external ground truth. This loop
makes the orchestration genuinely dynamic; it does not make the underlying
model omniscient.

### Why a graph instead of just calling functions with manual if/else?

You could hand-write the retry loop as a Python `while` loop with an `if
confidence < 50` check (in fact, `api.py`'s streaming endpoint does exactly
that — see "API layer" below, and why). The graph earns its place instead by
giving you, for free:

- **A typed, shared state object** (`GraphState`) instead of passing growing
  argument lists between functions.
- **A trace** of what happened at each step, including *why* a retry
  triggered (`state["trace"]`) — useful for debugging and for showing the
  workflow's reasoning to a user.
- **A structure that scales.** Adding a second, independent condition (e.g. "if
  Adversarial found strong contradictions, route straight to Judge and skip
  Synthesis") is another `add_conditional_edges` call, not a restructure of
  hand-written control flow.

## State (`src/state.py`)

`GraphState` is a `TypedDict` with one field per artifact the pipeline produces:
`claim` (input), `research_findings`, `adversarial_findings`, `synthesis`,
`verdict` / `confidence` / `reasoning` (final output), `trace` (a running log),
and `attempts` (how many times Research has run for this claim - `0` on the
first pass, incremented by `_prepare_retry_node` on a retry). Nodes only touch
the fields they own.

## Agents (`src/agents/`)

See [`src/agents/README.md`](../src/agents/README.md) for what each of the four
agents does and why the adversarial step exists as a separate agent rather than
being folded into research.

## Tools (`src/tools/`)

See [`src/tools/README.md`](../src/tools/README.md). There is one tool
(DuckDuckGo web search), shared by the Research and Adversarial agents.

## LLM (`src/llm.py`)

A single factory function, `get_llm()`, that returns a `ChatOllama` instance
configured from environment variables (`OLLAMA_MODEL`, `OLLAMA_BASE_URL`). Every
agent calls this same factory — there's one place to change if you want to swap
models, point at a remote Ollama instance, or give a specific agent a different
temperature.

## API layer (`api.py`)

A thin FastAPI wrapper exposing the same agents the CLI uses over HTTP for
`frontend/` — but the two endpoints get there differently:

- **`POST /api/check`** — runs `check_claim()` (the same function `cli.py`
  calls, which runs the *real* compiled graph including the retry loop) in a
  worker thread via `asyncio.to_thread`, and returns the full result as one
  JSON object once everything has finished. Simple, but the caller has no
  visibility into progress until it's all done.
- **`GET /api/check-stream?claim=...`** — this is what `frontend/` actually
  uses. It does **not** call the compiled graph, because LangGraph's
  `.invoke()` only returns once the whole run finishes, with no built-in hook
  to pause and report progress after each node. Instead, `_stream_check()` in
  `api.py` calls the four agent functions directly and **hand-mirrors** both
  the node order and the retry rule (`CONFIDENCE_THRESHOLD`/`MAX_ATTEMPTS`,
  imported from `graph.py` so the numbers can't drift out of sync) in a plain
  Python `while` loop, emitting an SSE event before/after each agent
  (`event: step`, `{"agent": "research", "state": "active" | "done"}`) and one
  `event: retry` when it loops back, finishing with `event: final`.

This is a known duplication: the retry *decision* exists in two places
(`graph.py`'s conditional edge, and a plain `if` in `_stream_check`) that have
to be kept in sync by hand if the rule ever changes. The proper fix is to have
`check-stream` consume LangGraph's own streaming mode (`app.stream(...,
stream_mode="updates")`, which yields a state update after every node the
*real* graph executes, retries included) instead of re-deriving the sequence -
left as a follow-up since it also changes how "active" vs. "done" per-agent
status would need to be derived (that mode reports "just finished", not
"about to start").

## Data flow example

1. **Research Agent** receives the claim, runs 3+ differently-phrased
   DuckDuckGo searches (see [`src/agents/README.md`](../src/agents/README.md#research-agents-search-strategy)),
   returns a bullet list of findings with source URLs.
2. **Adversarial Agent** receives the claim *and* the research findings, runs
   its own search(es) aimed at contradicting them, returns counter-evidence (or
   explicitly says it found none).
3. **Synthesis Agent** receives both bullet lists, writes one balanced brief
   (no verdict yet).
4. **Judge Agent** receives the claim and the brief, outputs a strict
   `VERDICT / CONFIDENCE / REASONING` block, parsed into the final state.

The CLI (`cli.py`) prints the trace and every intermediate artifact, so you can
see exactly how the system arrived at its verdict — not just the final answer.
