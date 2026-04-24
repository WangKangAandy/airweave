"""Normalize browser redirect targets after OAuth (success or error)."""

from typing import Optional
from urllib.parse import urlparse, urlunparse

from airweave.core.config import settings


def post_oauth_browser_return_url(
    redirect_url: Optional[str],
    *,
    readable_collection_id: str,
) -> str:
    """Normalize post-OAuth redirect so the SPA does not land on ``/`` (dashboard).

    When ``redirect_url`` is missing or only the app root, use
    ``/collections/<readable_collection_id>`` on the same origin as any provided URL,
    otherwise :func:`settings.app_url`.

    Args:
        redirect_url: Optional URL from init session overrides.
        readable_collection_id: Collection readable id from init session payload.

    Returns:
        Absolute URL suitable for a 303 ``Location`` header.
    """
    rid = (readable_collection_id or "").strip()
    fallback_base = (settings.app_url or "http://localhost:8080").rstrip("/")
    if not rid:
        return f"{fallback_base}/"

    collection_path = f"/collections/{rid}"
    if not redirect_url or not str(redirect_url).strip():
        return f"{fallback_base}{collection_path}"

    raw = str(redirect_url).strip()
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return f"{fallback_base}{collection_path}"

    path = parsed.path or "/"
    normalized = path.rstrip("/") or "/"
    if normalized == "/" or not path.startswith("/collections/"):
        return urlunparse(
            (parsed.scheme, parsed.netloc, collection_path, parsed.params, parsed.query, parsed.fragment)
        )
    return raw
