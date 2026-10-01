from unittest.mock import patch

import pytest

from app.clients.wechat_client import WechatClient
from app.core.config import settings
from app.core.exceptions import WechatLoginError


class FakeWechatResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class InvalidJsonWechatResponse(FakeWechatResponse):
    def json(self):
        raise ValueError("invalid JSON")


class FakeAsyncClient:
    def __init__(self, response):
        self._response = response
        self.request_url = None
        self.request_params = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def get(self, url, params):
        self.request_url = url
        self.request_params = params
        return self._response


@pytest.fixture
def wechat_settings(monkeypatch):
    monkeypatch.setattr(settings, "WECHAT_APP_ID", "test-app-id")
    monkeypatch.setattr(settings, "WECHAT_APP_SECRET", "test-app-secret")


@pytest.mark.asyncio
async def test_code_exchange_uses_wechat_contract_and_retains_only_openid(wechat_settings):
    client = FakeAsyncClient(
        FakeWechatResponse(
            {
                "openid": "wx-openid-1",
                "session_key": "must-not-be-retained",
            }
        )
    )

    with patch("app.clients.wechat_client.httpx.AsyncClient", return_value=client):
        session = await WechatClient().exchange_code("temporary-code")

    assert session.openid == "wx-openid-1"
    assert not hasattr(session, "session_key")
    assert client.request_params == {
        "appid": "test-app-id",
        "secret": "test-app-secret",
        "js_code": "temporary-code",
        "grant_type": "authorization_code",
    }


@pytest.mark.asyncio
async def test_code_exchange_rejects_wechat_error_payloads(wechat_settings):
    client = FakeAsyncClient(
        FakeWechatResponse({"errcode": 40029, "errmsg": "invalid code"})
    )

    with patch("app.clients.wechat_client.httpx.AsyncClient", return_value=client):
        with pytest.raises(WechatLoginError):
            await WechatClient().exchange_code("expired-code")


@pytest.mark.asyncio
async def test_code_exchange_rejects_non_json_wechat_responses(wechat_settings):
    client = FakeAsyncClient(InvalidJsonWechatResponse(None))

    with patch("app.clients.wechat_client.httpx.AsyncClient", return_value=client):
        with pytest.raises(WechatLoginError):
            await WechatClient().exchange_code("invalid-response-code")
