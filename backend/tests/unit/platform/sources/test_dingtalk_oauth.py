"""Unit tests for DingTalk OAuth helpers (HTTP mocked; no real AppSecret)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from airweave.platform.sources.dingtalk_oauth import (
    DINGTALK_USER_ME_URL,
    DINGTALK_USER_TOKEN_URL,
    exchange_dingtalk_authorization_code,
    fetch_dingtalk_union_id,
)


def _mock_async_client(*, post_response: MagicMock | None = None, get_response: MagicMock | None = None):
    """Build AsyncClient mock that supports async with + post/get."""
    instance = MagicMock()
    instance.post = AsyncMock(return_value=post_response) if post_response else AsyncMock()
    instance.get = AsyncMock(return_value=get_response) if get_response else AsyncMock()
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=None)
    return instance


@pytest.mark.asyncio
async def test_exchange_dingtalk_authorization_code_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"accessToken":"user-at-1"}'
    mock_resp.json.return_value = {"accessToken": "user-at-1"}

    client_instance = _mock_async_client(post_response=mock_resp)

    with patch("airweave.platform.sources.dingtalk_oauth.httpx.AsyncClient", return_value=client_instance):
        out = await exchange_dingtalk_authorization_code(
            code="auth-code-xyz",
            client_id="ding_test",
            client_secret="secret_test",
        )

    assert out.access_token == "user-at-1"
    assert out.token_type == "Bearer"
    client_instance.post.assert_awaited_once()
    call_kw = client_instance.post.await_args
    assert call_kw[0][0] == DINGTALK_USER_TOKEN_URL
    assert call_kw[1]["json"]["grantType"] == "authorization_code"
    assert call_kw[1]["json"]["code"] == "auth-code-xyz"


@pytest.mark.asyncio
async def test_exchange_dingtalk_authorization_code_non_2xx_raises():
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = '{"error":"invalid"}'

    client_instance = _mock_async_client(post_response=mock_resp)

    with patch("airweave.platform.sources.dingtalk_oauth.httpx.AsyncClient", return_value=client_instance):
        with pytest.raises(HTTPException) as exc:
            await exchange_dingtalk_authorization_code(
                code="bad",
                client_id="id",
                client_secret="sec",
            )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_exchange_dingtalk_authorization_code_missing_access_token_raises():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"{}"
    mock_resp.json.return_value = {}

    client_instance = _mock_async_client(post_response=mock_resp)

    with patch("airweave.platform.sources.dingtalk_oauth.httpx.AsyncClient", return_value=client_instance):
        with pytest.raises(HTTPException) as exc:
            await exchange_dingtalk_authorization_code(code="c", client_id="i", client_secret="s")
    assert exc.value.status_code == 400
    assert "accessToken" in exc.value.detail


@pytest.mark.asyncio
async def test_fetch_dingtalk_union_id_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"unionId":"uid-42"}'
    mock_resp.json.return_value = {"unionId": "uid-42"}

    client_instance = _mock_async_client(get_response=mock_resp)

    with patch("airweave.platform.sources.dingtalk_oauth.httpx.AsyncClient", return_value=client_instance):
        uid = await fetch_dingtalk_union_id("tok")

    assert uid == "uid-42"
    client_instance.get.assert_awaited_once()
    call_kw = client_instance.get.await_args
    assert call_kw[0][0] == DINGTALK_USER_ME_URL
    assert call_kw[1]["headers"]["x-acs-dingtalk-access-token"] == "tok"


@pytest.mark.asyncio
async def test_exchange_dingtalk_authorization_code_connect_error_retries_and_raises_502():
    req = httpx.Request("POST", DINGTALK_USER_TOKEN_URL)
    connect_error = httpx.ConnectError("simulated connect fail", request=req)

    client_instance = _mock_async_client()
    client_instance.post = AsyncMock(side_effect=connect_error)

    with patch("airweave.platform.sources.dingtalk_oauth.httpx.AsyncClient", return_value=client_instance):
        with pytest.raises(HTTPException) as exc:
            await exchange_dingtalk_authorization_code(
                code="auth-code-xyz",
                client_id="ding_test",
                client_secret="secret_test",
            )

    assert exc.value.status_code == 502
    assert "token endpoint" in str(exc.value.detail)
    assert client_instance.post.await_count == 3
