"""Evidence Synthesis Agent: merges supporting and adversarial findings into one balanced brief."""

from src.llm import get_llm

SYSTEM_PROMPT = """You are the Evidence Synthesis Agent in a fact-checking system.

You will receive a claim, supporting research findings, and adversarial
(counter-evidence) findings. Combine them into a single, balanced evidence brief:
- Summarize what supports the claim and what contradicts it, in separate sections.
- Note the strength/credibility of each side's sources.
- Do NOT give a final true/false verdict - that is the Judge Agent's job.
Keep it concise (under 300 words)."""


def run_synthesis_agent(claim: str, research_findings: str, adversarial_findings: str) -> str:
    llm = get_llm()
    user_message = (
        f"Claim: {claim}\n\n"
        f"Supporting research findings:\n{research_findings}\n\n"
        f"Adversarial / counter-evidence findings:\n{adversarial_findings}\n\n"
        "Produce the balanced evidence brief."
    )
    response = llm.invoke(
        [("system", SYSTEM_PROMPT), ("user", user_message)]
    )
    return response.content
