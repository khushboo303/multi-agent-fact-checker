# Multi-Agent AI Fact-Checking System

A LangGraph multi-agent claim-verification workflow: given a claim, four
specialized agents research it, adversarially challenge it, synthesize the
evidence, and render a judged verdict — all running on **free, local models via
Ollama** (no paid API keys required). Usable from the command line or from a
web UI (FastAPI + React).

```
claim → Research Agent → Adversarial Agent → Synthesis Agent → Judge Agent → verdict
              │                  │
              └── search_tool (DuckDuckGo, free) ──┘
```

The four agents always run **sequentially** — each one needs the previous
agent's output, so there's no parallelism to be had here (see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#orchestration-layer)).

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full design
rationale, and [`src/agents/README.md`](src/agents/README.md) /
[`src/tools/README.md`](src/tools/README.md) for what each piece does.

## Why these agents?

- **Research Agent** — gathers evidence *for* the claim via web search.
- **Adversarial Verification Agent** — actively tries to disprove the claim and
  scrutinizes the research findings, so the system doesn't just confirm
  whatever the first search turned up.
- **Evidence Synthesis Agent** — merges both sides into one neutral, balanced
  brief.
- **Judge Agent** — weighs the brief and renders a final verdict with a
  confidence score and reasoning.

## Tech stack

| Piece | Choice | Why |
|---|---|---|
| Agent orchestration | [LangGraph](https://langchain-ai.github.io/langgraph/) `StateGraph` | Typed shared state, a clear place to add branching/looping later, built-in tool-calling agent prebuilt (`create_react_agent`) |
| LLM | [Ollama](https://ollama.com) via `langchain-ollama` | Runs open models locally — completely free, no API key, no rate limits, private |
| Tool calling | LangChain `@tool` + `create_react_agent` | Standard tool-calling loop for the Research and Adversarial agents |
| Web search | [`duckduckgo-search`](https://pypi.org/project/duckduckgo-search/) | Free, no API key or signup required |
| Backend API | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) | Serves the graph over HTTP; a `GET /api/check-stream` SSE endpoint reports real per-agent progress |
| Frontend | [React](https://react.dev/) + [Vite](https://vite.dev/) | Claim input, live sequential agent progress, verdict card, expandable evidence sections |
| Config | `python-dotenv` + `.env` | Swap models / search settings without touching code |

## Requirements

- Python 3.10+
- Node.js + npm (only needed for the web frontend)
- [Ollama](https://ollama.com/download) installed and running locally
- A tool-calling-capable local model pulled, e.g.:
  ```bash
  ollama pull llama3.1
  ```
  (`llama3.1`, `qwen2.5`, and `mistral-nemo` are all known to support tool
  calling through Ollama; smaller/instruction-only models may not reliably
  call tools — if the Research/Adversarial agents never call `search_tool`,
  try a different model.)

## Setup

```bash
git clone <this-repo-url>
cd multi-agent-fact-checker

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # defaults are fine for a local Ollama install
```

Make sure Ollama is running (`ollama serve`, or just have the Ollama app open)
and the model from `.env` is pulled.

## Usage

### Option A: command line

```bash
# One-off claim from the command line
python cli.py "The Great Wall of China is visible from space with the naked eye."

# Or run interactively
python cli.py
```

Example output shape:

```
======================================================================
FINAL VERDICT
======================================================================
Verdict:    FALSE
Confidence: 85%
Reasoning:  Multiple reputable sources and astronaut testimony confirm the
            Great Wall is not distinguishable from low Earth orbit without
            aid; the myth predates spaceflight...
```

More example claims to try are in [`examples/sample_claims.txt`](examples/sample_claims.txt).

### Option B: web UI

Two servers, run in separate terminals.

**Backend** (from the project root, with the venv activated):

```bash
uvicorn api:app --reload --port 8000
```

**Frontend**:

```bash
cd frontend
npm install     # first time only
npm run dev
```

Open the URL Vite prints (`http://localhost:5173`), enter a claim, and hit
"Fact-check it." The page shows each agent going `pending → active → done` in
real order as the pipeline actually executes them — not a generic spinner —
followed by the verdict card and expandable Research / Adversarial / Synthesis
sections.

The frontend talks to the backend at `http://127.0.0.1:8000` (hardcoded in
`frontend/src/App.jsx` as `API_BASE`); both must be running.

## Running the tests

```bash
pip install pytest
pytest
```

The bundled test (`tests/test_graph.py`) only checks that the graph compiles
and contains the expected nodes — it doesn't call the LLM or the network, so it
runs instantly and requires no Ollama instance.

## Project layout

```
multi-agent-fact-checker/
├── cli.py                     # CLI entry point
├── api.py                     # FastAPI backend (POST /api/check, GET /api/check-stream)
├── frontend/                  # React + Vite web UI
│   └── src/App.jsx
├── docs/
│   └── ARCHITECTURE.md        # full design write-up
├── examples/
│   └── sample_claims.txt
├── src/
│   ├── agents/                # the four agents (+ README)
│   ├── tools/                 # search tool (+ README)
│   ├── graph.py               # orchestration layer (LangGraph StateGraph)
│   ├── llm.py                 # shared Ollama LLM factory
│   └── state.py               # shared GraphState schema
├── tests/
│   └── test_graph.py
├── .env.example
└── requirements.txt
```

## Known limitation: small local models can miss or misstate facts

Running everything on a free, local, relatively small model (e.g. `qwen2.5:7b`)
keeps this project free and private, but it caps result quality in two ways:

- **Search coverage**: the Research/Adversarial Agents only see whatever a
  handful of DuckDuckGo queries return. A real but less-obvious fact (e.g. a
  regional holiday, a units-conversion nuance) can simply not surface in the
  first few results, and the model has no way to know what it didn't see.
- **Model recall**: a 7B-class model doesn't reliably "know" enough on its own
  to catch a search gap, and can occasionally state a plausible-sounding but
  fabricated detail.

This isn't a bug in the pipeline — the graph, agents, and tool-calling all work
as designed. If you need higher accuracy, the two levers (see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)) are: use a larger/better local
model in `OLLAMA_MODEL` (if your machine has the RAM for it), or widen/tune the
Research Agent's search prompt in `src/agents/research_agent.py` further.

## Extending it

- **New tool** (e.g. Wikipedia, a fact-check database API): add a `@tool`
  function in `src/tools/`, then add it to the `tools=[...]` list in
  `src/agents/research_agent.py` / `adversarial_agent.py`.
- **Loop back on low confidence**: add a conditional edge in `src/graph.py`
  from `judge` back to `research` when `state["confidence"]` is below a
  threshold — see the note in `docs/ARCHITECTURE.md`.
- **Swap models per agent**: `get_llm()` in `src/llm.py` takes a `temperature`
  argument today; extend it to accept a model override if you want, e.g., a
  larger model just for the Judge.
