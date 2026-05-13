"""DingTalk OAuth2: user access token exchange (non-RFC form POST)."""

from __future__ import annotations

import asyncio
import logging

import httpx
from fastapi import HTTPException

from airweave.platform.auth.schemas import OAuth2TokenResponse

DINGTALK_USER_TOKEN_URL = "https://api.dingtalk.com/v1.0/oauth2/userAccessToken"
DINGTALK_USER_ME_URL = "https://api.dingtalk.com/v1.0/contact/users/me"
logger = logging.getLogger(__name__)


def _build_http_client() -> httpx.AsyncClient:
    """Build a client aligned with OAuth service patterns plus robust network defaults.

    - trust_env=False avoids inheriting unpredictable proxy env from runtime.
    - local_address='0.0.0.0' forces IPv4 source binding and avoids flaky IPv6 paths.
    """
    transport = httpx.AsyncHTTPTransport(retries=0, local_address="0.0.0.0")
    timeout = httpx.Timeout(connect=8.0, read=20.0, write=20.0, pool=20.0)
    return httpx.AsyncClient(timeout=timeout, transport=transport, trust_env=False)


async def exchange_dingtalk_authorization_code(
    *,
    code: str,
    client_id: str,
    client_secret: str,
) -> OAuth2TokenResponse:
    """Exchange DingTalk authorization code for a user access token (JSON request body)."""
    response: httpx.Response | None = None
    last_error: Exception | None = None
    for attempt in (1, 2, 3):
        try:
            async with _build_http_client() as client:
                response = await client.post(
                    DINGTALK_USER_TOKEN_URL,
                    json={
                        "clientId": client_id,
                        "clientSecret": client_secret,
                        "code": code,
                        "grantType": "authorization_code",
                    },
                    headers={"Content-Type": "application/json"},
                )
            break
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            last_error = exc
            logger.warning(
                "DingTalk token exchange network error (attempt=%s, endpoint=%s, error_type=%s): %s",
                attempt,
                DINGTALK_USER_TOKEN_URL,
                type(exc).__name__,
                exc,
            )
            if attempt < 3:
                await asyncio.sleep(0.4 * attempt)
            else:
                raise HTTPException(
                    status_code=502,
                    detail="Failed to reach DingTalk token endpoint (network/connectivity issue)",
                ) from exc

    if response is None:
        raise HTTPException(status_code=502, detail=f"DingTalk token exchange failed: {last_error}")
    if response.status_code < 200 or response.status_code >= 300:
        logger.warning(
            "DingTalk token exchange non-2xx (status=%s, body=%s)",
            response.status_code,
            response.text[:500],
        )
        raise HTTPException(
            status_code=400,
            detail=f"Failed to exchange DingTalk auth code: {response.text}",
        )
    data = response.json() if response.content else {}
    access = data.get("accessToken")
    if not access:
        raise HTTPException(status_code=400, detail="Missing accessToken in DingTalk token response")
    return OAuth2TokenResponse(access_token=str(access), token_type="Bearer")


async def fetch_dingtalk_union_id(access_token: str) -> str:
    """Return the authenticated user's unionId (for operator_union_id in config)."""
    response: httpx.Response | None = None
    for attempt in (1, 2, 3):
        try:
            async with _build_http_client() as client:
                response = await client.get(
                    DINGTALK_USER_ME_URL,
                    headers={
                        "x-acs-dingtalk-access-token": access_token,
                        "Content-Type": "application/json",
                    },
                )
            break
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning(
                "DingTalk profile fetch network error (attempt=%s, endpoint=%s, error_type=%s): %s",
                attempt,
                DINGTALK_USER_ME_URL,
                type(exc).__name__,
                exc,
            )
            if attempt < 3:
                await asyncio.sleep(0.4 * attempt)
            else:
                raise HTTPException(
                    status_code=502,
                    detail="Failed to reach DingTalk profile endpoint (network/connectivity issue)",
                ) from exc
    if response is None:
        raise HTTPException(status_code=502, detail="DingTalk profile request failed unexpectedly")
    if response.status_code < 200 or response.status_code >= 300:
        logger.warning(
            "DingTalk profile fetch non-2xx (status=%s, body=%s)",
            response.status_code,
            response.text[:500],
        )
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch DingTalk user profile: {response.text}",
        )
    data = response.json() if response.content else {}
    union_id = data.get("unionId")
    if not union_id:
        raise HTTPException(status_code=400, detail="Missing unionId in DingTalk user profile")
    return str(union_id)
