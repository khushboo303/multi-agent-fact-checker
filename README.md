# Multi-Agent AI Fact-Checking System

A LangGraph multi-agent claim-verification workflow: given a claim, four
specialized agents research it, adversarially challenge it, synthesize the
evidence, and render a judged verdict — all running on **free, local models via
Ollama** (no paid API keys required).

```
claim → Research Agent → Adversarial Agent → Synthesis Agent → Judge Agent → verdict
              │                  │
              └── search_tool (DuckDuckGo, free) ──┘
```

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
| Config | `python-dotenv` + `.env` | Swap models / search settings without touching code |

## Requirements

- Python 3.10+
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
├── cli.py                     # entry point
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
