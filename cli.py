"""Command-line entry point for the Multi-Agent AI Fact-Checking System.

Usage:
    python cli.py "The Great Wall of China is visible from space with the naked eye."
    python cli.py                 # prompts interactively
"""

import sys

from src.graph import check_claim


def main() -> None:
    if len(sys.argv) > 1:
        claim = " ".join(sys.argv[1:])
    else:
        claim = input("Enter a claim to fact-check: ").strip()

    if not claim:
        print("No claim provided.")
        return

    print(f"\nFact-checking claim: {claim!r}\n")
    result = check_claim(claim)

    print("=" * 70)
    print("TRACE")
    print("=" * 70)
    for step in result.get("trace", []):
        print(f"- {step}")

    print("\n" + "=" * 70)
    print("RESEARCH FINDINGS")
    print("=" * 70)
    print(result.get("research_findings", "(none)"))

    print("\n" + "=" * 70)
    print("ADVERSARIAL FINDINGS")
    print("=" * 70)
    print(result.get("adversarial_findings", "(none)"))

    print("\n" + "=" * 70)
    print("EVIDENCE SYNTHESIS")
    print("=" * 70)
    print(result.get("synthesis", "(none)"))

    print("\n" + "=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)
    print(f"Verdict:    {result.get('verdict', 'N/A')}")
    print(f"Confidence: {result.get('confidence', 'N/A')}%")
    print(f"Reasoning:  {result.get('reasoning', 'N/A')}")


if __name__ == "__main__":
    main()
