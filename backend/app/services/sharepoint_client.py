"""
SharePoint client — Phase 8.

Uploads a finalized export to a SharePoint document library via the
Microsoft Graph API, using the standard app-only (client credentials)
OAuth flow. Credentials come entirely from config (SHAREPOINT_TENANT_ID /
SHAREPOINT_CLIENT_ID / SHAREPOINT_CLIENT_SECRET / SHAREPOINT_SITE_URL) —
this module never hardcodes a tenant or secret.

DISCLOSED LIMITATION: this sandbox has no network access, so none of this
has been tested against a real Microsoft 365 tenant. What IS genuinely
testable without real credentials, and what isn't, is split deliberately:

  - `_build_upload_url()` — pure string formatting, no network. Tested for
    real (see tests/test_sharepoint_client.py).
  - `_graph_request()` — the actual HTTP call wrapper. Its CONNECTION-
    FAILURE handling (unreachable host, timeout) is tested for real against
    a genuinely-unreachable address, the same technique used for
    ollama_client.py in Phase 4. What can't be tested here: a real 401 from
    bad credentials, a real 404 from a wrong site URL, or the actual
    upload succeeding — those need a live tenant.
  - `_acquire_token()` — needs `msal`, which isn't installed in this
    sandbox (no network to install it). The import is deferred into the
    function itself so this module still imports cleanly without msal
    present; calling it without msal installed raises a clear
    SharePointSyncError rather than crashing at import time.

Every failure mode raises SharePointSyncError with an actionable message —
callers (export_service.py) catch this one exception type and degrade
gracefully (the Excel file itself is still generated and downloadable even
if SharePoint sync fails).
"""

from __future__ import annotations

from pathlib import Path

import requests

from app.core.config import settings

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]


class SharePointSyncError(Exception):
    """Raised for any SharePoint/Graph API failure — auth, site resolution, or upload."""


def _acquire_token() -> str:
    if not (settings.SHAREPOINT_TENANT_ID and settings.SHAREPOINT_CLIENT_ID and settings.SHAREPOINT_CLIENT_SECRET):
        raise SharePointSyncError(
            "SharePoint credentials are not configured (SHAREPOINT_TENANT_ID/"
            "SHAREPOINT_CLIENT_ID/SHAREPOINT_CLIENT_SECRET). Set these in .env "
            "to enable SharePoint sync."
        )

    try:
        import msal
    except ImportError as e:
        raise SharePointSyncError(
            "The 'msal' package is not installed. Run `pip install msal` to "
            "enable SharePoint sync."
        ) from e

    authority = f"https://login.microsoftonline.com/{settings.SHAREPOINT_TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        client_id=settings.SHAREPOINT_CLIENT_ID,
        client_credential=settings.SHAREPOINT_CLIENT_SECRET,
        authority=authority,
    )
    result = app.acquire_token_for_client(scopes=_GRAPH_SCOPE)

    if "access_token" not in result:
        raise SharePointSyncError(
            f"Failed to acquire a Graph API token: "
            f"{result.get('error_description', result.get('error', 'unknown error'))}"
        )
    return result["access_token"]


def _graph_request(method: str, url: str, token: str, **kwargs) -> requests.Response:
    """Thin wrapper translating connection-level failures into SharePointSyncError."""
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"

    try:
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    except requests.exceptions.ConnectionError as e:
        raise SharePointSyncError(f"Could not reach Microsoft Graph at {url}: connection failed.") from e
    except requests.exceptions.Timeout as e:
        raise SharePointSyncError(f"Microsoft Graph request to {url} timed out.") from e

    if response.status_code >= 400:
        raise SharePointSyncError(
            f"Microsoft Graph returned HTTP {response.status_code} for {method} {url}: "
            f"{response.text[:500]}"
        )
    return response


def _resolve_site_id(token: str, site_url: str) -> str:
    """
    Resolves a SharePoint site URL (e.g. https://contoso.sharepoint.com/sites/QA)
    into a Graph site id, via GET /sites/{hostname}:/{server-relative-path}.
    """
    if not site_url:
        raise SharePointSyncError("SHAREPOINT_SITE_URL is not configured.")

    stripped = site_url.replace("https://", "").replace("http://", "")
    if "/" not in stripped:
        raise SharePointSyncError(f"SHAREPOINT_SITE_URL '{site_url}' doesn't look like a full site URL.")
    hostname, path = stripped.split("/", 1)

    url = f"{_GRAPH_BASE}/sites/{hostname}:/{path}"
    response = _graph_request("GET", url, token)
    data = response.json()
    site_id = data.get("id")
    if not site_id:
        raise SharePointSyncError(f"Graph API response for site lookup had no 'id': {data}")
    return site_id


def _get_default_drive_id(token: str, site_id: str) -> str:
    url = f"{_GRAPH_BASE}/sites/{site_id}/drive"
    response = _graph_request("GET", url, token)
    data = response.json()
    drive_id = data.get("id")
    if not drive_id:
        raise SharePointSyncError(f"Graph API response for drive lookup had no 'id': {data}")
    return drive_id


def _build_upload_url(drive_id: str, folder: str, filename: str) -> str:
    """
    Pure string-formatting helper — builds the Graph API "upload content"
    URL for a small file (<4MB; this app's exports are always small
    spreadsheets, so the simple PUT-content endpoint is sufficient — large
    files would need Graph's resumable upload session API instead).
    """
    folder = folder.strip("/")
    path = f"{folder}/{filename}" if folder else filename
    return f"{_GRAPH_BASE}/drives/{drive_id}/root:/{path}:/content"


def upload_file(file_path: str | Path, filename: str) -> dict:
    """
    Uploads `file_path` to the configured SharePoint site's default
    document library, under SHAREPOINT_UPLOAD_FOLDER. Returns
    {"web_url": ..., "item_id": ...} on success. Raises SharePointSyncError
    on any failure — auth, site/drive resolution, or the upload itself.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise SharePointSyncError(f"File not found: {file_path}")

    token = _acquire_token()
    site_id = _resolve_site_id(token, settings.SHAREPOINT_SITE_URL)
    drive_id = _get_default_drive_id(token, site_id)
    upload_url = _build_upload_url(drive_id, settings.SHAREPOINT_UPLOAD_FOLDER, filename)

    with open(file_path, "rb") as f:
        content = f.read()

    response = _graph_request(
        "PUT", upload_url, token,
        data=content,
        headers={"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    )
    data = response.json()

    return {
        "web_url": data.get("webUrl", ""),
        "item_id": data.get("id", ""),
    }
