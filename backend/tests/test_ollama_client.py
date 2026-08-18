"""
Tests for app.services.ollama_client.

These hit a real (but deliberately wrong) URL to exercise the actual
requests-based connection-error path — no mocking of `requests` itself,
so this proves the error handling works against genuine network failures,
not just against a mocked exception type.
"""

import pytest

from app.services.ollama_client import default_llm_call, OllamaUnavailableError


def test_unreachable_daemon_raises_ollama_unavailable_error(monkeypatch):
    from app.core.config import settings

    # Port 1 is a genuine, always-refused connection on any normal machine —
    # this exercises the real requests.exceptions.ConnectionError path.
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://localhost:1")
    monkeypatch.setattr(settings, "OLLAMA_TIMEOUT_SECONDS", 2)

    with pytest.raises(OllamaUnavailableError) as exc_info:
        default_llm_call("test prompt")

    assert "Could not connect to Ollama" in str(exc_info.value)


def test_error_message_includes_configured_url(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://localhost:1")
    monkeypatch.setattr(settings, "OLLAMA_TIMEOUT_SECONDS", 2)

    with pytest.raises(OllamaUnavailableError) as exc_info:
        default_llm_call("test prompt")

    assert "localhost:1" in str(exc_info.value)
