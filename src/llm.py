"""Factory for the local LLM used by every agent.

All agents share the same Ollama-hosted model, configured via environment
variables so swapping models never requires touching agent code.
"""

import os

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()


def get_llm(temperature: float = 0.0) -> ChatOllama:
    model = os.getenv("OLLAMA_MODEL", "llama3.1")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return ChatOllama(model=model, base_url=base_url, temperature=temperature)
