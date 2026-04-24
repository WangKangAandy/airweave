#!/usr/bin/env python3
"""Minimal probe: verify DingTalk doc access with user token + unionId.

Goal:
    After unionId is already obtained, call official DingTalk API for a target
    alidocs URL and classify whether failure is likely a permission issue.

Usage (from backend/):
    export DINGTALK_USER_ACCESS_TOKEN='...'
    export DINGTALK_OPERATOR_UNION_ID='...'
    export DINGTALK_DOC_URL='https://alidocs.dingtalk.com/i/nodes/MyQA2dXW7edN241muMpLAmNPJzlwrZgb?utm_scene=person_space'
    poetry run python scripts/probe_dingtalk_doc_permission.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

import httpx

DINGTALK_API_BASE = "https://api.dingtalk.com"


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text[:2000]


def _looks_like_permission_error(status: int, body: Any) -> bool:
    if status in (401, 403):
        return True
    text = json.dumps(body, ensure_ascii=False) if isinstance(body, (dict, list)) else str(body)
    lowered = text.lower()
    keys = [
        "forbidden",
        "permission",
        "no permission",
        "access denied",
        "operator",
        "scope",
        "权限",
        "无权限",
    ]
    return any(k in lowered for k in keys)


def _looks_like_param_error(status: int, body: Any) -> bool:
    if status == 400:
        return True
    text = json.dumps(body, ensure_ascii=False) if isinstance(body, (dict, list)) else str(body)
    lowered = text.lower()
    keys = [
        "invalidparameter",
        "invalid parameter",
        "param",
        "参数",
        "notfound",
        "missing",
    ]
    return any(k in lowered for k in keys)


def _extract_node_token(url: str) -> str | None:
    m = re.search(r"/nodes/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


def _print_step(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main() -> int:
    access_token = os.environ.get("DINGTALK_USER_ACCESS_TOKEN", "").strip()
    union_id = os.environ.get("DINGTALK_OPERATOR_UNION_ID", "").strip()
    doc_url = os.environ.get("DINGTALK_DOC_URL", "").strip()

    if not access_token or not union_id or not doc_url:
        print(
            "Missing env vars: DINGTALK_USER_ACCESS_TOKEN, DINGTALK_OPERATOR_UNION_ID, DINGTALK_DOC_URL",
            file=sys.stderr,
        )
        return 1

    clean_url = doc_url.split("?", 1)[0]
    node_token = _extract_node_token(doc_url)
    headers = {
        "x-acs-dingtalk-access-token": access_token,
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=30.0) as client:
        _print_step("1) Baseline user profile check (/v1.0/contact/users/me)")
        me = client.get(f"{DINGTALK_API_BASE}/v1.0/contact/users/me", headers=headers)
        me_body = _safe_json(me)
        print("status:", me.status_code)
        print("body:", json.dumps(me_body, ensure_ascii=False, indent=2))
        if me.status_code != 200:
            print("\n结论：token 无法读取用户信息，先解决 token 本身问题。")
            return 2

        _print_step("2) Official wiki queryByUrl (with operatorId=unionId)")
        q1 = client.post(
            f"{DINGTALK_API_BASE}/v2.0/wiki/nodes/queryByUrl",
            params={"operatorId": union_id},
            json={"url": clean_url},
            headers=headers,
        )
        q1_body = _safe_json(q1)
        print("request: POST /v2.0/wiki/nodes/queryByUrl")
        print("params:", {"operatorId": union_id})
        print("json:", {"url": clean_url})
        print("status:", q1.status_code)
        print("body:", json.dumps(q1_body, ensure_ascii=False, indent=2))

        _print_step("3) Control queryByUrl (without operatorId)")
        q2 = client.post(
            f"{DINGTALK_API_BASE}/v2.0/wiki/nodes/queryByUrl",
            json={"url": clean_url},
            headers=headers,
        )
        q2_body = _safe_json(q2)
        print("request: POST /v2.0/wiki/nodes/queryByUrl")
        print("params: (none)")
        print("json:", {"url": clean_url})
        print("status:", q2.status_code)
        print("body:", json.dumps(q2_body, ensure_ascii=False, indent=2))

        if node_token:
            _print_step("4) Optional cross-check docs blocks (connector legacy path)")
            b = client.get(
                f"{DINGTALK_API_BASE}/v1.0/docs/{node_token}/blocks",
                params={"size": 1, "operatorUnionId": union_id},
                headers=headers,
            )
            b_body = _safe_json(b)
            print("request: GET /v1.0/docs/{node}/blocks?size=1&operatorUnionId=...")
            print("node:", node_token)
            print("status:", b.status_code)
            print("body:", json.dumps(b_body, ensure_ascii=False, indent=2))

    _print_step("Verdict")
    if q1.status_code == 200:
        print("结论：带 operatorId 的官方接口可访问，非权限阻断。优先排查主流程参数映射/回调落库。")
        return 0

    if _looks_like_permission_error(q1.status_code, q1_body):
        print("结论：高度疑似权限问题（operator 对目标文档或应用接口无可见/可读权限）。")
        return 10

    if _looks_like_param_error(q1.status_code, q1_body):
        print("结论：更像参数或资源标识问题（URL/接口字段/资源映射），不是纯权限问题。")
        return 11

    print("结论：未知失败类型，请结合响应体进一步确认。")
    return 12


if __name__ == "__main__":
    raise SystemExit(main())

