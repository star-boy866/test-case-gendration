"""
Ollama client — Phase 4.

Per Technology Policy A ("prefer local inference e.g. Ollama, vLLM" and
"no paid AI APIs"), this is a thin HTTP wrapper around a locally-running
Ollama daemon (OLLAMA_BASE_URL, default http://localhost:11434).

Every consumer of an LLM in this codebase (planning_agent.py,
generator_agent.py) depends on a plain `Callable[[str], str]`, not on this
module directly — `default_llm_call` below is just the production
implementation of that signature. This means:
  - Swapping providers (vLLM, a different local model, etc.) is a one-file
    change, satisfying the "architecture must remain model-agnostic"
    requirement.
  - Every other agent module is fully unit-testable with a fake
    Callable[[str], str], with no Ollama daemon required at all.

OllamaUnavailableError is raised (not a raw requests exception) whenever
the daemon can't be reached or returns a non-2xx response, so callers
(generation.py) can catch ONE clear exception type and return a helpful
error to the user instead of a raw connection-error stack trace.
"""

from __future__ import annotations

import json

import requests

from app.core.config import settings


class OllamaUnavailableError(Exception):
    """Raised when the configured Ollama daemon can't be reached or errors out."""


def default_llm_call(prompt: str, *, model: str | None = None) -> str:
    """
    Sends `prompt` to Ollama's /api/generate endpoint with streaming
    disabled and returns the raw text response. Callers are responsible
    for parsing structured output out of that text (see
    planning_agent.parse_planning_response / generator_agent.parse_generator_response).
    """
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": model or settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = requests.post(url, json=payload, timeout=settings.OLLAMA_TIMEOUT_SECONDS)
    except requests.exceptions.ConnectionError as e:
        raise OllamaUnavailableError(
            f"Could not connect to Ollama at {settings.OLLAMA_BASE_URL}. "
            f"Is the Ollama daemon running locally? (ollama serve)"
        ) from e
    except requests.exceptions.Timeout as e:
        raise OllamaUnavailableError(
            f"Ollama at {settings.OLLAMA_BASE_URL} did not respond within "
            f"{settings.OLLAMA_TIMEOUT_SECONDS}s."
        ) from e

    if response.status_code != 200:
        raise OllamaUnavailableError(
            f"Ollama returned HTTP {response.status_code}: {response.text[:500]}"
        )

    try:
        data = response.json()
    except json.JSONDecodeError as e:
        raise OllamaUnavailableError(
            f"Ollama response was not valid JSON: {response.text[:500]}"
        ) from e

    return data.get("response", "")
