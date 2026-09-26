# Architecture

## Orchestration layer

`src/graph.py` is the orchestration layer: it defines the shared `GraphState`
that flows between agents, wraps each agent as a graph node, and wires the
nodes into a single linear [LangGraph](https://langchain-ai.github.io/langgraph/)
`StateGraph`:

```
        ┌──────────┐     ┌─────────────┐     ┌───────────┐     ┌───────┐
 claim →│ Research │────▶│ Adversarial │────▶│ Synthesis │────▶│ Judge │──▶ verdict
        │  Agent   │     │   Agent     │     │   Agent   │     │ Agent │
        └──────────┘     └─────────────┘     └───────────┘     └───────┘
             │                   │
             └────── search_tool (DuckDuckGo) ──────┘
```

Each node is a plain Python function `(GraphState) -> dict` that reads whatever
fields it needs off the state and returns a partial update. LangGraph merges
that update into the running state before calling the next node — this is the
same pattern you'd use for a much larger graph (conditional branches, retries,
parallel fan-out), just applied to the simplest useful case: one path, no
branching.

**Execution is strictly sequential, not parallel.** Each node genuinely depends
on the previous one's output (Adversarial needs the Research findings,
Synthesis needs both, Judge needs the synthesis), so there's no independent
work to fan out even if the graph wanted to. A single claim always means 4
LLM calls in a row, which is why it takes noticeably longer than a single
model call — see "API layer" below for how the UI surfaces this honestly
instead of showing a generic spinner.

### Why a graph instead of just calling four functions in a row?

For this workflow's current shape, a plain function pipeline would do the same
thing. The graph earns its place because it gives you, for free and without
restructuring the agents:

- **A typed, shared state object** (`GraphState`) instead of passing growing
  argument lists between functions.
- **A trace** of what happened at each step (`state["trace"]`), useful for
  debugging and for showing the workflow's reasoning to a user.
- **A natural extension point.** The most likely next feature — "if the Judge's
  confidence is low, loop back to Research with a more targeted query" — is a
  conditional edge (`add_conditional_edges`) away, not a rewrite. Same for
  running Research and an independent Adversarial search in parallel, or adding
  a human-approval step before the final verdict.

If this project only ever needs the fixed four-step pipeline, that's a
reasonable place to stop; the graph is kept intentionally linear here to match
"don't complicate it more than the task needs."

## State (`src/state.py`)

`GraphState` is a `TypedDict` with one field per artifact the pipeline produces:
`claim` (input), `research_findings`, `adversarial_findings`, `synthesis`,
`verdict` / `confidence` / `reasoning` (final output), and `trace` (a running
log). Nodes only touch the fields they own.

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

A thin FastAPI wrapper around the same graph the CLI uses — it doesn't
reimplement any agent logic, just exposes it over HTTP for `frontend/`.

- **`POST /api/check`** — runs `check_claim()` (the same function `cli.py`
  calls) in a worker thread via `asyncio.to_thread`, and returns the full
  result as one JSON object once all four agents have finished. Simple, but
  the caller has no visibility into progress until it's all done.
- **`GET /api/check-stream?claim=...`** — calls the four agent functions
  directly (`run_research_agent`, `run_adversarial_agent`, etc. from
  `src/agents`) one at a time, the same order `graph.py` wires them in, and
  streams a Server-Sent Event before and after each one (`event: step`,
  `{"agent": "research", "state": "active" | "done"}`), finishing with one
  `event: final` carrying the complete result. This is what `frontend/` uses:
  it lets the UI show each agent going pending → active → done in the graph's
  real execution order, rather than a spinner that implies the agents might be
  running together.

Both endpoints run the *same* underlying agents — `check-stream` isn't a
different pipeline, just a differently-shaped way of observing the one graph
already described above.

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
