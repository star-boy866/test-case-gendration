"""
Tests for app.services.email_service.

Split per the module's own docstring: build_export_email() is a pure
function and is fully tested here. send_email()'s connection-failure
handling is tested against a genuinely-unreachable host:port (same
technique as test_ollama_client.py in Phase 4 and test_sharepoint_client.py
in this phase). Real SMTP auth/delivery needs an actual mail server, which
isn't available in this sandbox.
"""

import pytest

from app.services.email_service import build_export_email, send_email, EmailSendError


def test_subject_includes_report_and_cr_id():
    subject, _ = build_export_email(
        report_id="RPT-Demo", cr_id="CR-1", scenario_count=5, filename="x.xlsx",
    )
    assert "RPT-Demo" in subject
    assert "CR-1" in subject


def test_subject_omits_cr_id_when_not_provided():
    subject, _ = build_export_email(
        report_id="RPT-Demo", cr_id=None, scenario_count=5, filename="x.xlsx",
    )
    assert "RPT-Demo" in subject
    assert "(" not in subject


def test_body_renders_quality_score_when_provided():
    _, body = build_export_email(
        report_id="RPT-Demo", cr_id="CR-1", scenario_count=5,
        filename="x.xlsx", quality_score=0.92,
    )
    assert "0.92" in body


def test_body_renders_na_for_missing_quality_score_not_a_fabricated_value():
    _, body = build_export_email(
        report_id="RPT-Demo", cr_id="CR-1", scenario_count=5,
        filename="x.xlsx", quality_score=None,
    )
    assert "N/A" in body


def test_body_includes_sharepoint_link_when_provided():
    _, body = build_export_email(
        report_id="RPT-Demo", cr_id="CR-1", scenario_count=5,
        filename="x.xlsx", sharepoint_url="https://contoso.sharepoint.com/x.xlsx",
    )
    assert "https://contoso.sharepoint.com/x.xlsx" in body


def test_body_shows_not_synced_when_no_sharepoint_link():
    _, body = build_export_email(
        report_id="RPT-Demo", cr_id="CR-1", scenario_count=5,
        filename="x.xlsx", sharepoint_url=None,
    )
    assert "Not synced" in body


def test_send_email_with_no_recipients_raises_clean_error():
    with pytest.raises(EmailSendError):
        send_email([], "subject", "<html></html>")


def test_send_email_without_smtp_configured_raises_clean_error(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SMTP_HOST", "")

    with pytest.raises(EmailSendError) as exc_info:
        send_email(["a@example.com"], "subject", "<html></html>")
    assert "not configured" in str(exc_info.value)


def test_send_email_unreachable_host_raises_clean_error(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SMTP_HOST", "localhost")
    monkeypatch.setattr(settings, "SMTP_PORT", 1)  # genuinely unreachable
    monkeypatch.setattr(settings, "SMTP_USE_TLS", False)
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "")
    monkeypatch.setattr(settings, "EMAIL_FROM_ADDRESS", "noreply@example.com")
    monkeypatch.setattr(settings, "EMAIL_TIMEOUT_SECONDS", 2)

    with pytest.raises(EmailSendError) as exc_info:
        send_email(["a@example.com"], "subject", "<html></html>")
    assert "Could not connect" in str(exc_info.value)
