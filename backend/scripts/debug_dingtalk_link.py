#!/usr/bin/env python3
"""Minimal DingTalk API probe for debugging doc links vs OpenAPI paths.

Compares:
  A) Current connector path: GET /v1.0/docs/{id}/blocks (node id from URL)
  B) Wiki path: POST /v2.0/wiki/nodes/queryByUrl with full document URL
  C) Folder traversal via /v2.0/doc/spaces/{spaceId}/directories
  D) File content attempt via storage downloadInfos

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


def _extract_children(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract children list from directory API response shapes."""
    if not isinstance(data, dict):
        return []
    children = (
        data.get("children")
        or (data.get("data") or {}).get("children")
        or (data.get("result") or {}).get("children")
        or []
    )
    if not isinstance(children, list):
        return []
    return [item for item in children if isinstance(item, dict)]


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
        r3_json = _safe_json(r3)

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

        if not isinstance(r3_json, dict):
            _print_section("Done")
            print("Cannot continue folder traversal because queryByUrl response is not JSON object.")
            return 0
        node = r3_json.get("node") if isinstance(r3_json.get("node"), dict) else {}
        node_id = str(node.get("nodeId") or "")
        space_id = str(node.get("workspaceId") or "")
        node_type = str(node.get("type") or "").upper()
        if not (space_id and node_id):
            _print_section("Done")
            print("queryByUrl did not return workspaceId/nodeId; stop here.")
            return 0

        _print_section("5) GET /v2.0/doc/spaces/{spaceId}/directories (root listing)")
        root = client.get(
            f"{DINGTALK_API_BASE}/v2.0/doc/spaces/{space_id}/directories",
            params={"operatorId": operator_union_id, "maxResults": 200},
            headers=auth_headers,
        )
        root_body = _safe_json(root)
        print("status:", root.status_code)
        print("response:", json.dumps(root_body, ensure_ascii=False, indent=2))

        parent_dentry_id = node_id
        root_children = _extract_children(root_body) if isinstance(root_body, dict) else []
        for child in root_children:
            if str(child.get("dentryUuid") or "") == node_id and str(child.get("dentryId") or ""):
                parent_dentry_id = str(child.get("dentryId"))
                break

        if node_type != "FOLDER" and not bool(node.get("hasChildren")):
            print("Target is not folder; skip folder traversal.")
            _print_section("Done")
            return 0

        _print_section("6) GET /v2.0/doc/spaces/{spaceId}/directories (folder children)")
        sub = client.get(
            f"{DINGTALK_API_BASE}/v2.0/doc/spaces/{space_id}/directories",
            params={
                "operatorId": operator_union_id,
                "dentryId": parent_dentry_id,
                "maxResults": 200,
            },
            headers=auth_headers,
        )
        sub_body = _safe_json(sub)
        print("mapped parent_dentry_id:", parent_dentry_id)
        print("status:", sub.status_code)
        print("response:", json.dumps(sub_body, ensure_ascii=False, indent=2))
        if sub.status_code != 200 or not isinstance(sub_body, dict):
            _print_section("Done")
            print("Folder listing failed; cannot verify file count/content.")
            return 0

        children = _extract_children(sub_body)
        files = [c for c in children if str(c.get("dentryType") or "").lower() != "folder"]
        print(f"folder_total_items={len(children)} file_items={len(files)}")

        _print_section("7) Content probe: /storage/.../downloadInfos/query per file")
        content_success = 0
        for idx, item in enumerate(files, 1):
            name = str(item.get("name") or item.get("title") or f"file-{idx}")
            dentry_id = str(item.get("dentryId") or "")
            print(f"\n[{idx}] {name} dentryId={dentry_id}")
            if not dentry_id:
                print("  - skip: missing dentryId")
                continue
            info = client.post(
                f"{DINGTALK_API_BASE}/v1.0/storage/spaces/{space_id}/dentries/{dentry_id}/downloadInfos/query",
                params={"unionId": operator_union_id},
                json={"option": {"preferIntranet": False}},
                headers={**auth_headers, "Content-Type": "application/json"},
            )
            info_body = _safe_json(info)
            print("  downloadInfos status:", info.status_code)
            if info.status_code != 200:
                if isinstance(info_body, dict):
                    print("  code:", info_body.get("code"))
                    print("  message:", info_body.get("message"))
                else:
                    print("  body:", info_body)
                continue

            sig = info_body.get("headerSignatureInfo") if isinstance(info_body, dict) else None
            resource_urls = sig.get("resourceUrls") if isinstance(sig, dict) else []
            resource_headers = sig.get("headers") if isinstance(sig, dict) else {}
            if not isinstance(resource_urls, list) or not resource_urls:
                print("  - empty resourceUrls")
                continue

            got_content = False
            for resource_url in resource_urls[:1]:
                rr = client.get(resource_url, headers=resource_headers or {})
                print("  resource fetch status:", rr.status_code)
                if rr.status_code != 200:
                    continue
                text_preview = (rr.text or "").strip()[:160]
                if text_preview:
                    got_content = True
                    print("  content preview:", text_preview.replace("\n", "\\n"))
                    break
            if got_content:
                content_success += 1

        _print_section("8) Summary")
        print(f"files_discovered={len(files)} files_with_content_preview={content_success}")
        if len(files) > 0 and content_success == 0:
            print("No file content could be fetched. Usually this is permission/org-level gating.")

    _print_section("Done")
    print(
        "Interpretation: if (2) fails with Version/400 but (3) succeeds, "
        "the node id from alidocs URLs is not a /v1.0/docs doc id — "
        "use wiki APIs or map queryByUrl → correct doc resource id."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
