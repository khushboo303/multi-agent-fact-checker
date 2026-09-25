"""Judge Agent: renders the final verdict from the synthesized evidence brief."""

import re
from typing import Tuple

from src.llm import get_llm

SYSTEM_PROMPT = """You are the Judge Agent in a fact-checking system - the final decision maker.

You will receive a claim and a balanced evidence brief (supporting + contradicting
evidence). Weigh the evidence and render a verdict.

You MUST respond in exactly this format, with no extra text before or after:

VERDICT: <one of TRUE, FALSE, PARTIALLY TRUE, UNVERIFIABLE>
CONFIDENCE: <a number from 0 to 100>
REASONING: <2-4 sentences explaining the verdict, referencing the strongest evidence>"""

_VERDICT_RE = re.compile(r"VERDICT:\s*(.+)")
_CONFIDENCE_RE = re.compile(r"CONFIDENCE:\s*(\d+)")
_REASONING_RE = re.compile(r"REASONING:\s*(.+)", re.DOTALL)


def _parse(text: str) -> Tuple[str, str, str]:
    verdict_match = _VERDICT_RE.search(text)
    confidence_match = _CONFIDENCE_RE.search(text)
    reasoning_match = _REASONING_RE.search(text)

    verdict = verdict_match.group(1).strip() if verdict_match else "UNVERIFIABLE"
    confidence = confidence_match.group(1).strip() if confidence_match else "N/A"
    reasoning = reasoning_match.group(1).strip() if reasoning_match else text.strip()

    return verdict, confidence, reasoning


def run_judge_agent(claim: str, synthesis: str) -> Tuple[str, str, str]:
    llm = get_llm()
    user_message = f"Claim: {claim}\n\nEvidence brief:\n{synthesis}\n\nRender your verdict."
    response = llm.invoke([("system", SYSTEM_PROMPT), ("user", user_message)])
    return _parse(response.content)
