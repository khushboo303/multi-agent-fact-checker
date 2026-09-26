"""FastAPI backend exposing the fact-checking graph over HTTP for the React frontend.

Run with:
    uvicorn api:app --reload --port 8000
"""

import asyncio
import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# The four agent functions, called directly (not via the graph) so /api/check-stream
# can run them one at a time and report progress between each - see _stream_check().
from src.agents import (
    run_adversarial_agent,
    run_judge_agent,
    run_research_agent,
    run_synthesis_agent,
)
# The same function cli.py calls - used by the simple, non-streaming /api/check.
# CONFIDENCE_THRESHOLD/MAX_ATTEMPTS are imported (not re-defined) so the retry
# rule below can't silently drift out of sync with the real graph in graph.py.
from src.graph import CONFIDENCE_THRESHOLD, MAX_ATTEMPTS, check_claim

app = FastAPI(title="Multi-Agent Fact-Checker API")

# Without this, the browser blocks the frontend (localhost:5173) from calling this
# API (localhost:8000) at all - different ports count as different origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Shape of the JSON body POST /api/check expects.
class ClaimRequest(BaseModel):
    claim: str


# Shape of the JSON both POST /api/check and the "final" SSE event return.
class ClaimResponse(BaseModel):
    claim: str
    trace: list[str]
    research_findings: str
    adversarial_findings: str
    synthesis: str
    verdict: str
    confidence: str
    reasoning: str


# Simple liveness check - lets the frontend (or you, via curl) confirm the backend
# is actually up before trying to fact-check anything.
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# One-shot endpoint: call it, wait, get the whole result back in a single response.
# Not used by the frontend (which needs live progress) - kept as the simple option
# for any other caller that just wants a plain request/response.
@app.post("/api/check", response_model=ClaimResponse)
async def check(request: ClaimRequest) -> ClaimResponse:
    claim = request.claim.strip()
    if not claim:
        return ClaimResponse(
            claim=claim,
            trace=[],
            research_findings="",
            adversarial_findings="",
            synthesis="",
            verdict="N/A",
            confidence="N/A",
            reasoning="No claim provided.",
        )

    # check_claim() makes blocking LLM/HTTP calls, so run it off the event loop
    # thread to keep the server responsive to other requests.
    result = await asyncio.to_thread(check_claim, claim)

    return ClaimResponse(
        claim=claim,
        trace=result.get("trace", []),
        research_findings=result.get("research_findings", ""),
        adversarial_findings=result.get("adversarial_findings", ""),
        synthesis=result.get("synthesis", ""),
        verdict=result.get("verdict", "N/A"),
        confidence=result.get("confidence", "N/A"),
        reasoning=result.get("reasoning", "N/A"),
    )


# Formats one Server-Sent Event: an "event: <name>" line naming it, a "data: <json>"
# line carrying the payload, and a blank line marking the end of this message - the
# exact text format EventSource on the frontend knows how to parse.
def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# Generator (not a route itself) that drives the four agents one at a time and
# yields an SSE string after each yield point. GET /api/check-stream below streams
# whatever this yields straight to the browser as it happens.
#
# This mirrors graph.py's node order and retry rule by hand instead of running the
# actual compiled graph, because LangGraph's .invoke() only returns once the whole
# run finishes - it has no built-in way to pause and report progress after each
# node. (LangGraph's .stream() *can* emit an update after every node, which would
# let this call the real graph instead of duplicating its logic - left as a
# follow-up since it changes how "active" vs "done" is tracked.)
async def _stream_check(claim: str):
    """Runs the same four agents as check_claim(), but one at a time with an SSE
    event emitted before and after each - so the frontend can show real sequential
    progress instead of a single opaque wait. Also mirrors graph.py's retry loop:
    if Judge's confidence is below CONFIDENCE_THRESHOLD, it goes back to Research
    (with a note about why the last attempt fell short) instead of finishing."""
    try:
        attempt = 0
        while True:
            retry_context = None
            temperature = 0.0
            if attempt > 0:
                temperature = 0.4
                retry_context = (
                    f"NOTE: this is a retry. A previous pass on this claim reached "
                    f"{confidence}% confidence, below the {CONFIDENCE_THRESHOLD}% bar "
                    f"this system requires, with this reasoning: \"{reasoning}\"\n"
                    "Don't just repeat the same searches - try different angles or "
                    "more specific sub-questions that might close that gap."
                )

            # Research Agent: searches the web for evidence supporting the claim.
            yield _sse("step", {"agent": "research", "state": "active"})
            research_findings = await asyncio.to_thread(
                run_research_agent, claim, retry_context, temperature
            )
            yield _sse("step", {"agent": "research", "state": "done"})

            # Adversarial Agent: given the claim + research findings, actively searches
            # for counter-evidence and flaws in what Research found.
            yield _sse("step", {"agent": "adversarial", "state": "active"})
            adversarial_findings = await asyncio.to_thread(
                run_adversarial_agent, claim, research_findings
            )
            yield _sse("step", {"agent": "adversarial", "state": "done"})

            # Synthesis Agent: merges both sides into one balanced evidence brief.
            # No tools, no web search - a single plain LLM call.
            yield _sse("step", {"agent": "synthesis", "state": "active"})
            synthesis = await asyncio.to_thread(
                run_synthesis_agent, claim, research_findings, adversarial_findings
            )
            yield _sse("step", {"agent": "synthesis", "state": "done"})

            # Judge Agent: reads the brief and renders the final verdict/confidence/
            # reasoning. Also a single plain LLM call, no tools.
            yield _sse("step", {"agent": "judge", "state": "active"})
            verdict, confidence, reasoning = await asyncio.to_thread(
                run_judge_agent, claim, synthesis
            )
            yield _sse("step", {"agent": "judge", "state": "done"})

            try:
                confidence_int = int(confidence)
            except (TypeError, ValueError):
                confidence_int = 100  # unparseable - don't retry on that alone

            attempt += 1
            if confidence_int < CONFIDENCE_THRESHOLD and attempt < MAX_ATTEMPTS:
                # Tell the frontend why it's about to see the agents run again,
                # then loop back to the top instead of falling through to "final".
                yield _sse("retry", {"attempt": attempt, "confidence": confidence})
                continue
            break

        # Everything finished - send the complete result once, which is what the
        # frontend's "final" event listener is waiting for.
        yield _sse(
            "final",
            {
                "claim": claim,
                "research_findings": research_findings,
                "adversarial_findings": adversarial_findings,
                "synthesis": synthesis,
                "verdict": verdict,
                "confidence": confidence,
                "reasoning": reasoning,
            },
        )
    except Exception as exc:  # noqa: BLE001 - surface the error to the frontend
        # Any agent/LLM/network failure lands here instead of crashing the stream -
        # the frontend's "error" listener shows this message and stops loading.
        yield _sse("error", {"message": str(exc)})


# Streaming endpoint the React frontend actually uses. Unlike /api/check, this
# takes the claim as a query param (?claim=...) because EventSource can only make
# GET requests - it has no way to send a JSON body.
@app.get("/api/check-stream")
async def check_stream(claim: str):
    claim = claim.strip()
    # StreamingResponse keeps the HTTP connection open and sends each string
    # _stream_check() yields to the client as soon as it's produced, instead of
    # buffering everything and sending one response at the end.
    return StreamingResponse(_stream_check(claim), media_type="text/event-stream")
