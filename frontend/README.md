# Frontend

React + Vite web UI for the [multi-agent fact-checker](../README.md).

## Run it

Requires the FastAPI backend running first (from the project root):

```bash
source ../.venv/bin/activate
uvicorn api:app --reload --port 8000
```

Then, in this directory:

```bash
npm install     # first time only
npm run dev
```

Open the printed URL (`http://localhost:5173`).

## What it does

- `src/App.jsx` is the whole app: a claim input, a progress view driven by the
  backend's `GET /api/check-stream` SSE endpoint (one agent shown active at a
  time, in real execution order — see [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md#api-layer-apipy)),
  and a results view (verdict card + expandable evidence sections).
- `API_BASE` at the top of `src/App.jsx` points at `http://127.0.0.1:8000` —
  change it if you run the backend on a different host/port.
- Built with the default Vite React template (Oxlint, no TypeScript, no
  React Compiler) — nothing here is templated beyond what `App.jsx`/`App.css`
  actually use.
