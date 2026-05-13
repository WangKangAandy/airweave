"""Unit tests for post-OAuth browser redirect URL normalization."""

import pytest

from airweave.api.v1.endpoints.source_connections import _post_oauth_browser_return_url


class _FakeSettings:
    """Minimal settings stub; only ``app_url`` is used by the helper."""

    def __init__(self, app_url: str) -> None:
        self.app_url = app_url


@pytest.mark.parametrize(
    ("redirect", "expected_suffix"),
    [
        (None, "http://app.test:8080/collections/doc-col-1"),
        ("", "http://app.test:8080/collections/doc-col-1"),
        ("   ", "http://app.test:8080/collections/doc-col-1"),
    ],
)
def test_missing_redirect_falls_back_to_settings_and_collection(
    monkeypatch: pytest.MonkeyPatch, redirect: str | None, expected_suffix: str
) -> None:
    monkeypatch.setattr(
        "airweave.api.v1.endpoints.source_connections.settings",
        _FakeSettings("http://app.test:8080"),
    )
    out = _post_oauth_browser_return_url(redirect, readable_collection_id="doc-col-1")
    assert out == expected_suffix


def test_app_root_replaced_with_collection_on_same_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: app root ``/`` must not send users to the dashboard route."""
    monkeypatch.setattr(
        "airweave.api.v1.endpoints.source_connections.settings",
        _FakeSettings("http://localhost:8080"),
    )
    out = _post_oauth_browser_return_url(
        "http://192.168.24.40:8080/",
        readable_collection_id="musadocument-bf94br",
    )
    assert out == "http://192.168.24.40:8080/collections/musadocument-bf94br"


def test_preserves_existing_collection_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "airweave.api.v1.endpoints.source_connections.settings",
        _FakeSettings("http://app.test:8080"),
    )
    url = "https://other.test:9000/collections/abc-1?x=1"
    assert _post_oauth_browser_return_url(url, readable_collection_id="ignored") == url
