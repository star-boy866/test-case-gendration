"""
Tests for app.services.sharepoint_client.

Split per the module's own docstring: the pure URL-building function is
tested directly; the connection-failure handling is tested against a
genuinely-unreachable address (same technique as test_ollama_client.py in
Phase 4). Real auth/upload success needs a live Microsoft 365 tenant and
`msal` installed, neither of which is available in this sandbox.
"""

import pytest

from app.services.sharepoint_client import (
    _build_upload_url,
    _graph_request,
    _resolve_site_id,
    _acquire_token,
    SharePointSyncError,
)


def test_build_upload_url_with_folder():
    url = _build_upload_url("drive123", "SIT-QA-Exports", "RPT-1_session5.xlsx")
    assert url == "https://graph.microsoft.com/v1.0/drives/drive123/root:/SIT-QA-Exports/RPT-1_session5.xlsx:/content"


def test_build_upload_url_without_folder():
    url = _build_upload_url("drive123", "", "file.xlsx")
    assert url == "https://graph.microsoft.com/v1.0/drives/drive123/root:/file.xlsx:/content"


def test_build_upload_url_strips_leading_trailing_slashes_on_folder():
    url = _build_upload_url("drive123", "/SIT-QA-Exports/", "file.xlsx")
    assert url == "https://graph.microsoft.com/v1.0/drives/drive123/root:/SIT-QA-Exports/file.xlsx:/content"


def test_graph_request_unreachable_host_raises_sharepoint_sync_error():
    with pytest.raises(SharePointSyncError):
        _graph_request("GET", "http://localhost:1/sites/foo", token="fake-token")


def test_acquire_token_without_credentials_raises_clean_error(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SHAREPOINT_TENANT_ID", "")
    monkeypatch.setattr(settings, "SHAREPOINT_CLIENT_ID", "")
    monkeypatch.setattr(settings, "SHAREPOINT_CLIENT_SECRET", "")

    with pytest.raises(SharePointSyncError) as exc_info:
        _acquire_token()
    assert "not configured" in str(exc_info.value)


def test_resolve_site_id_with_empty_url_raises():
    with pytest.raises(SharePointSyncError):
        _resolve_site_id("fake-token", "")


def test_resolve_site_id_with_malformed_url_raises():
    with pytest.raises(SharePointSyncError):
        _resolve_site_id("fake-token", "not-a-valid-url")
