#!/usr/bin/env python3
"""Minimal DingTalk API probe for debugging doc links vs OpenAPI paths.

Compares:
  A) Current connector path: GET /v1.0/docs/{id}/blocks (node id from URL)
  B) Wiki path: POST /v2.0/wiki/nodes/queryByUrl with full document URL

Usage (from backend/):

  export DINGTALK_APP_KEY=dingxxxx
  export DINGTALK_APP_SECRET=xxxx
  export DINGTALK_DOC_URL='https://alidocs.dingtalk.com/i/nodes/...'
  # Optional — some wiki APIs require operator context:
  export DINGTALK_OPERATOR_UNION_ID='your_union_id'

  poetry run python scripts/debug_dingtalk_link.py

Do not commit credentials. Rotate secrets if they were pasted into chat logs.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

import httpx

DINGTALK_API_BASE = "https://api.dingtalk.com"


def _extract_node_token(url: str) -> str | None:
    """Same idea as DingTalkEntryResolver: /nodes/<token>."""
    m = re.search(r"/nodes/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


def _print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text[:2000]


def main() -> int:
    app_key = os.environ.get("DINGTALK_APP_KEY", "").strip()
    app_secret = os.environ.get("DINGTALK_APP_SECRET", "").strip()
    doc_url = os.environ.get("DINGTALK_DOC_URL", "").strip()
    operator_union_id = os.environ.get("DINGTALK_OPERATOR_UNION_ID", "").strip()

    if not app_key or not app_secret or not doc_url:
        print(
            "Missing env: DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_DOC_URL",
            file=sys.stderr,
        )
        return 1

    token_payload = {"appKey": app_key, "appSecret": app_secret}

    with httpx.Client(timeout=30.0) as client:
        _print_section("1) POST /v1.0/oauth2/accessToken")
        r = client.post(
            f"{DINGTALK_API_BASE}/v1.0/oauth2/accessToken",
            json=token_payload,
            headers={"Content-Type": "application/json"},
        )
        print("status:", r.status_code)
        body = _safe_json(r)
        print("body:", json.dumps(body, ensure_ascii=False, indent=2) if isinstance(body, dict) else body)
        if r.status_code != 200 or not isinstance(body, dict):
            print("Cannot continue without accessToken.", file=sys.stderr)
            return 2
        access_token = body.get("accessToken")
        if not access_token:
            print("accessToken missing in response.", file=sys.stderr)
            return 2

        auth_headers = {"x-acs-dingtalk-access-token": access_token}

        node_token = _extract_node_token(doc_url)
        print()
        print("Extracted /nodes/ token:", node_token)

        _print_section("2) GET /v1.0/docs/{docId}/blocks (connector validate path)")
        if node_token:
            path = f"/v1.0/docs/{node_token}/blocks"
            r2 = client.get(
                f"{DINGTALK_API_BASE}{path}",
                params={"size": 1},
                headers=auth_headers,
            )
            print("request:", "GET", path, "?size=1")
            print("status:", r2.status_code)
            print("body:", json.dumps(_safe_json(r2), ensure_ascii=False, indent=2))
        else:
            print("Skip — could not parse node id from DINGTALK_DOC_URL")

        _print_section("3) POST /v2.0/wiki/nodes/queryByUrl (official link → node)")
        params: dict[str, str] = {}
        if operator_union_id:
            # Docs often use operatorId (unionId) for wiki scope; try common name.
            params["operatorId"] = operator_union_id
        r3 = client.post(
            f"{DINGTALK_API_BASE}/v2.0/wiki/nodes/queryByUrl",
            params=params or None,
            json={"url": doc_url.split("?", 1)[0]},
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        print("request: POST /v2.0/wiki/nodes/queryByUrl", "params:", params or "(none)")
        print("body url field (path only):", doc_url.split("?", 1)[0])
        print("status:", r3.status_code)
        print("response:", json.dumps(_safe_json(r3), ensure_ascii=False, indent=2))

        if operator_union_id:
            _print_section("4) POST /v2.0/wiki/nodes/queryByUrl (full URL with query string)")
            r4 = client.post(
                f"{DINGTALK_API_BASE}/v2.0/wiki/nodes/queryByUrl",
                params={"operatorId": operator_union_id},
                json={"url": doc_url},
                headers={**auth_headers, "Content-Type": "application/json"},
            )
            print("status:", r4.status_code)
            print("response:", json.dumps(_safe_json(r4), ensure_ascii=False, indent=2))

    _print_section("Done")
    print(
        "Interpretation: if (2) fails with Version/400 but (3) succeeds, "
        "the node id from alidocs URLs is not a /v1.0/docs doc id — "
        "use wiki APIs or map queryByUrl → correct doc resource id."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
