#!/usr/bin/env python3
"""最小可行性验证：Confluence Server / Data Center「站点根 URL + PAT」直连 /rest/api。

不属于 Airweave 产品代码。验证与 Airweave 同步语义一致的两段式链路：

1. **发现页面 ID**（等同同步里「搜索/列举」）：`GET /rest/api/content/search?cql=…`
   失败时 fallback：`GET /rest/api/content?spaceKey=…&type=page`（先 `GET /rest/api/space`）。
2. **按 ID 拉正文**（等同同步里「拉 storage 再落盘」）：
   `GET /rest/api/content/{id}?expand=body.storage,version,space`

任一步失败或 Discover 不到任何 page，则 **适配前结论为不可行**（须先修权限/URL/版本）。

与 **Confluence Cloud**（`api.atlassian.com` + `/wiki/api/v2`）**不兼容**。

环境变量
----------
  CONFLUENCE_SITE_URL   站点根 URL
  CONFLUENCE_PAT        PAT（Bearer）

可选
----------
  CONFLUENCE_VERIFY_TLS  默认 true；内网自签可调 false
  --pat-file PATH        从文件读 PAT（chmod 600），避免出现在进程列表

用法
----------
  cd backend && export CONFLUENCE_SITE_URL='…' CONFLUENCE_PAT='…'
  poetry run python scripts/confluence_site_pat_smoke.py

  poetry run python scripts/confluence_site_pat_smoke.py --site '…' --pat-file ~/.confluence_pat

勿将 PAT 提交仓库；泄露请轮换。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx


def _normalize_site(url: str) -> str:
    u = url.strip().rstrip("/")
    if not u.startswith(("http://", "https://")):
        raise SystemExit(f"CONFLUENCE_SITE_URL must start with http(s)://, got: {url!r}")
    return u


def _auth_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/json",
        # 部分实例对写操作要求；只读探测带上无妨
        "X-Atlassian-Token": "no-check",
    }


def _print_json(label: str, data: Any, max_chars: int = 1200) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n… (truncated)"
    print(f"\n=== {label} ===\n{text}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("环境变量")[0].strip())
    parser.add_argument(
        "--site",
        default=os.environ.get("CONFLUENCE_SITE_URL", ""),
        help="站点根 URL（或设 CONFLUENCE_SITE_URL）",
    )
    parser.add_argument(
        "--pat",
        default=os.environ.get("CONFLUENCE_PAT", ""),
        help="PAT（或设 CONFLUENCE_PAT；与 --pat-file 二选一）",
    )
    parser.add_argument(
        "--pat-file",
        default="",
        help="从本地文件读取 PAT（推荐，避免出现在 argv）",
    )
    parser.add_argument(
        "--cql",
        default="type=page",
        help='CQL 查询（默认 type=page），用于 content/search',
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="关闭 TLS 校验（等同 CONFLUENCE_VERIFY_TLS=false）",
    )
    args = parser.parse_args()

    pat = args.pat.strip()
    if args.pat_file:
        try:
            pat = Path(args.pat_file).read_text(encoding="utf-8").strip()
        except OSError as e:
            print(f"无法读取 --pat-file: {e}", file=sys.stderr)
            return 2

    if not args.site or not pat:
        print(
            "需要 --site 与 --pat/--pat-file（或环境变量 CONFLUENCE_SITE_URL / CONFLUENCE_PAT）",
            file=sys.stderr,
        )
        return 2

    base = _normalize_site(args.site)
    verify_tls = os.environ.get("CONFLUENCE_VERIFY_TLS", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    if args.insecure:
        verify_tls = False

    headers = _auth_headers(pat)

    print(f"Base URL: {base}")
    print(f"TLS verify: {verify_tls}")

    with httpx.Client(timeout=60.0, verify=verify_tls) as client:
        print("\n—— 阶段 A：发现页面（search / 列举，对应同步「找 id」）——")

        # 1) 当前用户（部分版本/权限配置可能 404，不致命）
        r_user = client.get(f"{base}/rest/api/user/current", headers=headers)
        print(f"\nGET /rest/api/user/current -> {r_user.status_code}")
        if r_user.status_code == 200:
            uj = r_user.json()
            _print_json("user/current", uj)
            if uj.get("type") == "anonymous":
                print(
                    "\n警告：当前被识别为匿名用户；Bearer PAT 可能无效、过期或未被实例接受。"
                    "有效 PAT 下通常应显示真实用户而非 anonymous。",
                    file=sys.stderr,
                )
        elif r_user.status_code != 404:
            print(r_user.text[:500])

        # 2) 列举空间（分页常见）
        r_spaces = client.get(f"{base}/rest/api/space?limit=5", headers=headers)
        print(f"\nGET /rest/api/space?limit=5 -> {r_spaces.status_code}")
        if r_spaces.is_success:
            spaces_payload = r_spaces.json()
            _print_json("spaces (first page)", spaces_payload)
        else:
            print(r_spaces.text[:800])
            print(
                "\nCONFLUENCE_SITE_PAT_FEASIBILITY: FAIL —— 无法列举 space（鉴权或权限异常）。",
                file=sys.stderr,
            )
            return 1

        space_results = spaces_payload.get("results") or []
        first_space_key: str | None = None
        if space_results and isinstance(space_results[0], dict):
            first_space_key = space_results[0].get("key")

        # 3) CQL 发现 page（与重构文档 §6.2 对齐的探测）
        cql = args.cql
        search_url = f"{base}/rest/api/content/search?cql={quote(cql)}&limit=5"
        r_search = client.get(search_url, headers=headers)
        print(f"\nGET /rest/api/content/search?cql={cql}&limit=5 -> {r_search.status_code}")

        pages: list[Any]
        if r_search.is_success:
            search_payload = r_search.json()
            _print_json("content/search", search_payload)
            pages = search_payload.get("results") or []
        else:
            print(r_search.text[:800])
            pages = []
            if first_space_key:
                list_url = f"{base}/rest/api/content"
                r_list = client.get(
                    list_url,
                    params={"spaceKey": first_space_key, "type": "page", "limit": 5},
                    headers=headers,
                )
                print(
                    f"\nFallback GET /rest/api/content?spaceKey={first_space_key}&type=page&limit=5 "
                    f"-> {r_list.status_code}"
                )
                if r_list.is_success:
                    list_payload = r_list.json()
                    _print_json("content list (by spaceKey)", list_payload)
                    pages = list_payload.get("results") or []
                else:
                    print(r_list.text[:800])

            if not pages:
                print(
                    "\n提示：CQL search 失败且按 space 列举 content 无结果。"
                    "请核对 Confluence 版本、PAT 权限与 REST 是否对当前用户开放。",
                    file=sys.stderr,
                )
                print(
                    "\nCONFLUENCE_SITE_PAT_FEASIBILITY: FAIL —— Discover 阶段失败。",
                    file=sys.stderr,
                )
                return 1

        if not pages and first_space_key:
            list_url = f"{base}/rest/api/content"
            r_list = client.get(
                list_url,
                params={"spaceKey": first_space_key, "type": "page", "limit": 5},
                headers=headers,
            )
            print(
                f"\n补充 GET /rest/api/content?spaceKey={first_space_key}&type=page&limit=5 "
                f"-> {r_list.status_code}"
            )
            if r_list.is_success:
                list_payload = r_list.json()
                _print_json("content list (by spaceKey)", list_payload)
                pages = list_payload.get("results") or []
            else:
                print(r_list.text[:800])

        if not pages:
            print(
                "\nCONFLUENCE_SITE_PAT_FEASIBILITY: FAIL —— 未发现任何 page（Discover 为空，同步也无法拉数）。",
                file=sys.stderr,
            )
            return 1

        first_id = pages[0].get("id")
        if not first_id:
            print(
                "\nCONFLUENCE_SITE_PAT_FEASIBILITY: FAIL —— 结果中无 page id。",
                file=sys.stderr,
            )
            return 1

        print("\n—— 阶段 B：按 id 拉取正文（expand=body.storage，对应同步「拉内容」）——")

        # 4) 取正文 storage（与「拉 HTML 再落盘」链路等价的前半段）
        expand = "body.storage,version,space"
        r_page = client.get(
            f"{base}/rest/api/content/{first_id}",
            params={"expand": expand},
            headers=headers,
        )
        print(f"\nGET /rest/api/content/{first_id}?expand={expand} -> {r_page.status_code}")
        if not r_page.is_success:
            print(r_page.text[:800])
            print(
                "\nCONFLUENCE_SITE_PAT_FEASIBILITY: FAIL —— 无法拉取单页详情。",
                file=sys.stderr,
            )
            return 1

        detail = r_page.json()
        body_block = detail.get("body") or {}
        storage = body_block.get("storage")
        if storage is None:
            print(
                "\nCONFLUENCE_SITE_PAT_FEASIBILITY: FAIL —— 响应中无 body.storage（expand 未生效或被策略拒绝）。",
                file=sys.stderr,
            )
            return 1

        body = storage if isinstance(storage, dict) else {}
        snippet = (body.get("value") or "")[:400]
        _print_json("page detail (metadata + body preview)", {**detail, "body": {"storage": {"value": snippet + ("…" if len(snippet) == 400 else "")}}})

        print(
            "\nCONFLUENCE_SITE_PAT_FEASIBILITY: PASS —— "
            "已用 PAT 完成「CQL/search 或 space 列举 → 取得 page id → expand 拉到 body.storage」。"
            "可进入 Airweave 源适配（空正文页面 value 可为空，属正常）。"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
