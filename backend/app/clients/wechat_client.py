from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.exceptions import WechatLoginError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class WechatSession:
    """Only the stable identity returned by WeChat is retained."""

    openid: str


class WechatClient:
    """Exchange a short-lived mini-program login code for an openid."""

    async def exchange_code(self, code: str) -> WechatSession:
        if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
            raise WechatLoginError(
                detail="WeChat login is not configured",
                status_code=503,
            )

        try:
            async with httpx.AsyncClient(timeout=settings.WECHAT_TIMEOUT) as client:
                response = await client.get(
                    settings.WECHAT_LOGIN_URL,
                    params={
                        "appid": settings.WECHAT_APP_ID,
                        "secret": settings.WECHAT_APP_SECRET,
                        "js_code": code,
                        "grant_type": "authorization_code",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            logger.error("WeChat code exchange request failed", error=str(error))
            raise WechatLoginError(
                detail="Unable to verify the WeChat login code",
                status_code=503,
            ) from error

        try:
            payload = response.json()
        except ValueError as error:
            logger.error("WeChat returned a non-JSON login response", error=str(error))
            raise WechatLoginError(
                detail="Unable to verify the WeChat login code",
                status_code=503,
            ) from error

        error_code = payload.get("errcode")
        openid = payload.get("openid")
        if error_code or not isinstance(openid, str) or not openid:
            logger.warning(
                "WeChat rejected login code",
                error_code=error_code,
                error_message=payload.get("errmsg"),
            )
            raise WechatLoginError()

        return WechatSession(openid=openid)


_wechat_client: WechatClient | None = None


def get_wechat_client() -> WechatClient:
    """Get the shared WeChat API client."""

    global _wechat_client
    if _wechat_client is None:
        _wechat_client = WechatClient()
    return _wechat_client
