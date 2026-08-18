"""
Email service — Phase 8.

Sends an HTML-formatted notification when an export is finalized,
containing the execution summary the Master System Prompt specifies (CR
ID, total scenarios, quality/evaluation score) and — once SharePoint sync
succeeds — a direct link to the SharePoint artifact.

Uses Python's standard-library `smtplib`/`email` rather than a third-party
mail API, per the Technology Policy's "no paid AI APIs, mandatory
subscriptions" spirit extended sensibly to email: any SMTP server (a
corporate relay, Office 365, Gmail with an app password, etc.) works
without a new paid dependency.

DISCLOSED LIMITATION: no SMTP server is reachable from this sandbox, so
actually sending mail is untested here. What's split out and testable
without one:

  - `build_export_email()` — pure function producing the subject + HTML
    body. Tested for real (see tests/test_email_service.py).
  - `send_email()`'s CONNECTION-FAILURE handling is tested for real against
    a genuinely-unreachable host:port, the same technique used for
    ollama_client.py (Phase 4) and sharepoint_client.py (this phase).
    What can't be tested here: real SMTP auth, a real send succeeding, or
    actual delivery — those need a real mail server.
"""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings


class EmailSendError(Exception):
    """Raised for any email delivery failure — connection, auth, or send."""


def build_export_email(
    *,
    report_id: str,
    cr_id: str | None,
    scenario_count: int,
    filename: str,
    quality_score: float | None = None,
    sharepoint_url: str | None = None,
) -> tuple[str, str]:
    """
    Pure function: returns (subject, html_body). No I/O.

    quality_score is optional and deliberately NOT computed by this
    module or by export_service.py: a session's Refinement Grid can span
    multiple generation calls (each with its own Critic score) plus
    manually-added rows with no score at all, so there is no single
    honest number to report unless the caller has one in mind (e.g. the
    frontend's most recently-seen Critic score for this session). Passing
    None renders "N/A" rather than a fabricated aggregate.
    """
    subject = f"SIT/QA Test Scenarios Ready — {report_id}" + (f" ({cr_id})" if cr_id else "")
    quality_display = f"{quality_score:.2f}" if quality_score is not None else "N/A"

    sharepoint_row = (
        f'<tr><td style="padding:4px 12px 4px 0;color:#475569;">SharePoint</td>'
        f'<td><a href="{sharepoint_url}">{sharepoint_url}</a></td></tr>'
        if sharepoint_url else
        '<tr><td style="padding:4px 12px 4px 0;color:#475569;">SharePoint</td>'
        '<td style="color:#94a3b8;">Not synced</td></tr>'
    )

    html_body = f"""\
<html>
  <body style="font-family:Calibri,Arial,sans-serif;color:#1e293b;">
    <h2 style="color:#1C3BB0;">SIT / QA Test Scenario Export Complete</h2>
    <table style="border-collapse:collapse;">
      <tr><td style="padding:4px 12px 4px 0;color:#475569;">Report ID</td><td><b>{report_id}</b></td></tr>
      <tr><td style="padding:4px 12px 4px 0;color:#475569;">CR ID</td><td>{cr_id or "(not provided)"}</td></tr>
      <tr><td style="padding:4px 12px 4px 0;color:#475569;">Total Scenarios</td><td>{scenario_count}</td></tr>
      <tr><td style="padding:4px 12px 4px 0;color:#475569;">Quality Score</td><td>{quality_display}</td></tr>
      <tr><td style="padding:4px 12px 4px 0;color:#475569;">Filename</td><td>{filename}</td></tr>
      {sharepoint_row}
    </table>
    <p style="color:#64748b;font-size:12px;margin-top:24px;">
      This is an automated notification from the Healthcare NL-to-Test-Case
      Generation platform. Quality Score (when shown) reflects the Critic's
      automated checklist evaluation from generation, not a human sign-off.
    </p>
  </body>
</html>
"""
    return subject, html_body


def send_email(to_addresses: list[str], subject: str, html_body: str) -> None:
    if not to_addresses:
        raise EmailSendError("No recipient addresses provided.")
    if not settings.SMTP_HOST:
        raise EmailSendError(
            "Email is not configured (SMTP_HOST is empty). Set SMTP_HOST/"
            "SMTP_PORT/SMTP_USER/SMTP_PASSWORD/EMAIL_FROM_ADDRESS in .env "
            "to enable email notifications."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM_ADDRESS or settings.SMTP_USER
    msg["To"] = ", ".join(to_addresses)
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.EMAIL_TIMEOUT_SECONDS) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], to_addresses, msg.as_string())
    except (ConnectionRefusedError, OSError) as e:
        raise EmailSendError(
            f"Could not connect to SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT}: {e}"
        ) from e
    except smtplib.SMTPAuthenticationError as e:
        raise EmailSendError(f"SMTP authentication failed for user '{settings.SMTP_USER}': {e}") from e
    except smtplib.SMTPException as e:
        raise EmailSendError(f"SMTP error while sending: {e}") from e


def send_export_notification(
    *,
    to_addresses: list[str],
    report_id: str,
    cr_id: str | None,
    scenario_count: int,
    filename: str,
    quality_score: float | None = None,
    sharepoint_url: str | None = None,
) -> None:
    subject, html_body = build_export_email(
        report_id=report_id, cr_id=cr_id, scenario_count=scenario_count,
        quality_score=quality_score, filename=filename, sharepoint_url=sharepoint_url,
    )
    send_email(to_addresses, subject, html_body)
