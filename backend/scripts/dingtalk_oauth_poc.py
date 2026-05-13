#!/usr/bin/env python3
"""POC: DingTalk browser login (OAuth) → user access token → unionId via /contact/users/me.

This is standalone (not Airweave). Use it to verify your app has「钉钉登录与分享」
callback URL + scopes before wiring the same flow into the product.

Flow (official):
  1) GET https://login.dingtalk.com/oauth2/auth?...  → user signs in
  2) Redirect to your redirect_uri with authCode (and sometimes `code` in older docs)
  3) POST https://api.dingtalk.com/v1.0/oauth2/userAccessToken
  4) GET  https://api.dingtalk.com/v1.0/contact/users/me  with user accessToken in header

Prerequisites:
  - Developer console → your app →「钉钉登录与分享」→ add callback URL exactly as printed (byte-for-byte).
  - Remote SSH + browser on another machine: set DINGTALK_OAUTH_PUBLIC_HOST to the host your *browser*
    can reach (e.g. LAN IP of the server). Register that same URL in DingTalk. The script listens on
    0.0.0.0 by default in that mode so the redirect hits this process.

Env:
  DINGTALK_APP_KEY       AppKey (client_id)
  DINGTALK_APP_SECRET    AppSecret
  Optional:
  DINGTALK_OAUTH_PORT    default 8765
  DINGTALK_OAUTH_SCOPE   default "openid"
  DINGTALK_OAUTH_PUBLIC_HOST  If set (e.g. 192.168.24.40), redirect_uri becomes
                              http://<PUBLIC_HOST>:<port>/callback and bind address defaults to 0.0.0.0.
  DINGTALK_OAUTH_BIND    Listen address; default 0.0.0.0 when PUBLIC_HOST set, else 127.0.0.1.
  DINGTALK_OAUTH_HOST    Only used when PUBLIC_HOST is empty: host in redirect_uri (= bind host).

Usage (LAN / SSH server, browser on laptop):

  export DINGTALK_APP_KEY='dingxxx'
  export DINGTALK_APP_SECRET='xxx'
  export DINGTALK_OAUTH_PUBLIC_HOST='192.168.24.40'
  python3 scripts/dingtalk_oauth_poc.py
  # Then open the printed auth URL in a browser on a machine that can reach 192.168.24.40:8765

Do not commit secrets. Rotate AppSecret if exposed.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

API = "https://api.dingtalk.com"
LOGIN = "https://login.dingtalk.com/oauth2/auth"


def _parse_query(path: str) -> dict[str, list[str]]:
    q = urlparse(path).query
    return parse_qs(q)


def _make_callback_handler(ctx: dict[str, Any]) -> type[BaseHTTPRequestHandler]:
    """Build a BaseHTTPRequestHandler subclass that stores OAuth result in ctx."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"[oauth-callback] {fmt % args}")

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not Found")
                return

            qs = _parse_query(self.path)
            # DingTalk docs: success uses authCode= ; some examples use code=
            auth_code = (qs.get("authCode") or qs.get("code") or [None])[0]
            err = (qs.get("error") or [None])[0]
            state_back = (qs.get("state") or [None])[0]

            ctx["result"] = {
                "authCode": auth_code,
                "error": err,
                "state": state_back,
                "raw_query": parsed.query,
            }
            ctx["event"].set()

            body = (
                "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
                "<body><p>授权已完成，请回到运行脚本的终端查看 unionId 等输出。</p>"
                "<p>可关闭此页。</p></body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main() -> int:
    app_key = os.environ.get("DINGTALK_APP_KEY", "").strip()
    app_secret = os.environ.get("DINGTALK_APP_SECRET", "").strip()
    port = int(os.environ.get("DINGTALK_OAUTH_PORT", "8765"))
    public_host = os.environ.get("DINGTALK_OAUTH_PUBLIC_HOST", "").strip()
    scope = os.environ.get("DINGTALK_OAUTH_SCOPE", "openid").strip()

    if not app_key or not app_secret:
        print("Set DINGTALK_APP_KEY and DINGTALK_APP_SECRET", flush=True)
        return 1

    if public_host:
        redirect_host = public_host
        bind_raw = os.environ.get("DINGTALK_OAUTH_BIND", "0.0.0.0").strip()
        bind_host = bind_raw or "0.0.0.0"
    else:
        bind_host = os.environ.get("DINGTALK_OAUTH_HOST", "127.0.0.1").strip() or "127.0.0.1"
        redirect_host = bind_host

    redirect_uri = f"http://{redirect_host}:{port}/callback"
    state = secrets.token_urlsafe(16)

    params = {
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "client_id": app_key,
        "scope": scope,
        "state": state,
        "prompt": "consent",
    }
    auth_url = f"{LOGIN}?{urlencode(params)}"

    print("=" * 72, flush=True)
    print("1) Register this EXACT redirect URL in 钉钉开发者后台 → 钉钉登录与分享:", flush=True)
    print(f"   {redirect_uri}", flush=True)
    print("=" * 72, flush=True)
    print(
        f"2) HTTP server listening on {bind_host}:{port} (redirect uses host {redirect_host}).",
        flush=True,
    )
    if public_host:
        print(
            "   Open the auth URL below in a browser on your PC (same LAN as the server).",
            flush=True,
        )
    else:
        print("2b) Opening local browser if available…", flush=True)
    print(auth_url, flush=True)
    print()

    ctx: dict[str, Any] = {"event": threading.Event(), "result": {}}
    handler_cls = _make_callback_handler(ctx)
    server = HTTPServer((bind_host, port), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    if not public_host:
        try:
            webbrowser.open(auth_url)
        except Exception as e:
            print(f"webbrowser.open failed ({e}); open the URL manually.", flush=True)

    if not ctx["event"].wait(timeout=300):
        print("Timeout: no callback in 300s.", flush=True)
        server.shutdown()
        return 2

    server.shutdown()
    result = ctx.get("result") or {}
    print("Callback query parsed:", json.dumps(result, ensure_ascii=False, indent=2), flush=True)

    if result.get("error"):
        print("OAuth error from DingTalk:", result.get("error"), flush=True)
        return 3

    expected_state = state
    got_state = result.get("state")
    if got_state and got_state != expected_state:
        print("WARNING: state mismatch (possible CSRF). Aborting token exchange.", flush=True)
        return 4

    code = result.get("authCode")
    if not code:
        print("No authCode/code in callback.", flush=True)
        return 5

    payload = {
        "clientId": app_key,
        "clientSecret": app_secret,
        "code": code,
        "grantType": "authorization_code",
    }
    print("\nPOST /v1.0/oauth2/userAccessToken ...", flush=True)
    with httpx.Client(timeout=30.0) as client:
        tr = client.post(
            f"{API}/v1.0/oauth2/userAccessToken",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        print("status:", tr.status_code, flush=True)
        body = tr.json() if tr.headers.get("content-type", "").startswith("application/json") else {}
        print(json.dumps(body, ensure_ascii=False, indent=2))
        if tr.status_code != 200:
            print("Token exchange failed.", flush=True)
            return 6

        user_token = body.get("accessToken")
        if not user_token:
            print("No accessToken in userAccessToken response.", flush=True)
            return 7

        print("\nGET /v1.0/contact/users/me (unionId in response) ...", flush=True)
        ur = client.get(
            f"{API}/v1.0/contact/users/me",
            headers={
                "x-acs-dingtalk-access-token": user_token,
                "Content-Type": "application/json",
            },
        )
        print("status:", ur.status_code, flush=True)
        ubody = ur.json() if ur.headers.get("content-type", "").startswith("application/json") else {}
        print(json.dumps(ubody, ensure_ascii=False, indent=2))

        if ur.status_code == 200 and isinstance(ubody, dict):
            uid = ubody.get("unionId")
            print("\n--- For Airweave `operator_union_id` field ---", flush=True)
            print(f"unionId: {uid}", flush=True)
        else:
            print("\nUser profile call failed — check app permissions (通讯录 / 个人用户信息).", flush=True)
            return 8

    print("\nPOC OK. Next: wire this flow into Airweave source connection.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
