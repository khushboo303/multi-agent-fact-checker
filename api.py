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

from src.agents import (
    run_adversarial_agent,
    run_judge_agent,
    run_research_agent,
    run_synthesis_agent,
)
from src.graph import check_claim

app = FastAPI(title="Multi-Agent Fact-Checker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ClaimRequest(BaseModel):
    claim: str


class ClaimResponse(BaseModel):
    claim: str
    trace: list[str]
    research_findings: str
    adversarial_findings: str
    synthesis: str
    verdict: str
    confidence: str
    reasoning: str


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


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


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _stream_check(claim: str):
    """Runs the same four agents as check_claim(), but one at a time with an SSE
    event emitted before and after each - so the frontend can show real sequential
    progress instead of a single opaque wait."""
    try:
        yield _sse("step", {"agent": "research", "state": "active"})
        research_findings = await asyncio.to_thread(run_research_agent, claim)
        yield _sse("step", {"agent": "research", "state": "done"})

        yield _sse("step", {"agent": "adversarial", "state": "active"})
        adversarial_findings = await asyncio.to_thread(
            run_adversarial_agent, claim, research_findings
        )
        yield _sse("step", {"agent": "adversarial", "state": "done"})

        yield _sse("step", {"agent": "synthesis", "state": "active"})
        synthesis = await asyncio.to_thread(
            run_synthesis_agent, claim, research_findings, adversarial_findings
        )
        yield _sse("step", {"agent": "synthesis", "state": "done"})

        yield _sse("step", {"agent": "judge", "state": "active"})
        verdict, confidence, reasoning = await asyncio.to_thread(
            run_judge_agent, claim, synthesis
        )
        yield _sse("step", {"agent": "judge", "state": "done"})

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
        yield _sse("error", {"message": str(exc)})


@app.get("/api/check-stream")
async def check_stream(claim: str):
    claim = claim.strip()
    return StreamingResponse(_stream_check(claim), media_type="text/event-stream")
