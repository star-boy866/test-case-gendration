"""
LLM Provider abstraction.

Provides a clean interface for LLM calls with provider-agnostic
implementation. Currently supports Groq (with OpenAI-compatible API).

Usage:
    provider = get_llm_provider()
    response = provider.call("Your prompt here")
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.config import settings


class LLMUnavailableError(Exception):
    """Raised when the configured LLM provider can't be reached."""


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def call(self, prompt: str, *, model: str | None = None) -> str:
        """Send a prompt and return the response text."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is reachable."""
        ...


class GroqProvider(LLMProvider):
    """
    Groq API provider using OpenAI-compatible chat completions API.

    Configuration:
        GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL,
        GROQ_TIMEOUT_SECONDS, GROQ_MAX_RETRIES, GROQ_MAX_TOKENS
    """

    def __init__(self):
        self.api_key = getattr(settings, "GROQ_API_KEY", "") or getattr(settings, "GROK_API_KEY", "")
        self.model = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
        self.base_url = getattr(settings, "GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        self.timeout = getattr(settings, "GROQ_TIMEOUT_SECONDS", 90)
        self.max_retries = getattr(settings, "GROQ_MAX_RETRIES", 3)
        self.max_tokens = getattr(settings, "GROQ_MAX_TOKENS", 4096)

        if not self.api_key:
            raise LLMUnavailableError(
                "GROQ_API_KEY is not configured. Set it in .env."
            )

    def call(self, prompt: str, *, model: str | None = None) -> str:
        import json
        import requests
        import time

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
            "temperature": 0.3,  # Low temperature for deterministic output
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url, json=payload, headers=headers,
                    timeout=self.timeout,
                )

                if response.status_code == 429:
                    # Rate limited — exponential backoff
                    wait = min(2 ** attempt, 30)
                    time.sleep(wait)
                    continue

                if response.status_code != 200:
                    raise LLMUnavailableError(
                        f"Groq API returned HTTP {response.status_code}: "
                        f"{response.text[:500]}"
                    )

                data = response.json()
                return data["choices"][0]["message"]["content"]

            except requests.exceptions.ConnectionError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise LLMUnavailableError(
                    f"Could not connect to Groq API at {self.base_url}: {e}"
                ) from e
            except requests.exceptions.Timeout as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise LLMUnavailableError(
                    f"Groq API timed out after {self.timeout}s: {e}"
                ) from e
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                raise LLMUnavailableError(
                    f"Invalid response from Groq API: {e}"
                ) from e

        raise LLMUnavailableError(
            f"Groq API failed after {self.max_retries} retries. "
            f"Last error: {last_error}"
        )

    def is_available(self) -> bool:
        try:
            self.call("Say 'ok'.", model=self.model)
            return True
        except LLMUnavailableError:
            return False


def get_llm_provider() -> LLMProvider:
    """
    Factory function: returns the configured LLM provider.

    Dispatches on the LLM_PROVIDER setting.
    """
    provider_name = getattr(settings, "LLM_PROVIDER", "groq").lower()

    if provider_name in ("grok", "groq"):
        return GroqProvider()
    else:
        raise LLMUnavailableError(
            f"Unknown LLM_PROVIDER: '{provider_name}'. "
            f"Supported: groq"
        )


def get_llm_call():
    """
    Returns a Callable[[str], str] compatible with the existing pipeline
    interface (ollama_client.default_llm_call signature).
    """
    provider = get_llm_provider()
    return provider.call
