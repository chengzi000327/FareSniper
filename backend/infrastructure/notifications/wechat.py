from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from backend.config import settings


@dataclass(frozen=True)
class WechatSession:
    open_id: str
    session_key: str
    union_id: str | None = None


class WechatApiError(RuntimeError):
    def __init__(self, message: str, *, errcode: int | None = None) -> None:
        super().__init__(message)
        self.errcode = errcode


_access_token: str | None = None
_access_token_expires_at = 0.0
_access_token_lock = asyncio.Lock()


def _require_credentials() -> None:
    if not settings.wechat_mini_app_id or not settings.wechat_mini_app_secret:
        raise WechatApiError("wechat mini program credentials are not configured")


async def exchange_login_code(
    code: str, *, client: httpx.AsyncClient | None = None
) -> WechatSession:
    _require_credentials()
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=settings.wechat_request_timeout_seconds)
    try:
        response = await http.get(
            f"{settings.wechat_api_base_url.rstrip('/')}/sns/jscode2session",
            params={
                "appid": settings.wechat_mini_app_id,
                "secret": settings.wechat_mini_app_secret,
                "js_code": code,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errcode"):
            raise WechatApiError(
                str(payload.get("errmsg") or "wechat login failed"),
                errcode=int(payload["errcode"]),
            )
        open_id = str(payload.get("openid") or "").strip()
        session_key = str(payload.get("session_key") or "").strip()
        if not open_id or not session_key:
            raise WechatApiError("wechat login response missing identity")
        return WechatSession(
            open_id=open_id,
            session_key=session_key,
            union_id=payload.get("unionid"),
        )
    except httpx.HTTPError as exc:
        raise WechatApiError(f"wechat login request failed: {exc}") from exc
    finally:
        if owns_client:
            await http.aclose()


async def _fetch_access_token(
    *, client: httpx.AsyncClient | None = None, force: bool = False
) -> str:
    global _access_token, _access_token_expires_at
    _require_credentials()
    now = time.monotonic()
    if not force and _access_token and now < _access_token_expires_at:
        return _access_token
    async with _access_token_lock:
        now = time.monotonic()
        if not force and _access_token and now < _access_token_expires_at:
            return _access_token
        owns_client = client is None
        http = client or httpx.AsyncClient(
            timeout=settings.wechat_request_timeout_seconds
        )
        try:
            response = await http.get(
                f"{settings.wechat_api_base_url.rstrip('/')}/cgi-bin/token",
                params={
                    "grant_type": "client_credential",
                    "appid": settings.wechat_mini_app_id,
                    "secret": settings.wechat_mini_app_secret,
                },
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("errcode"):
                raise WechatApiError(
                    str(payload.get("errmsg") or "wechat token failed"),
                    errcode=int(payload["errcode"]),
                )
            token = str(payload.get("access_token") or "").strip()
            if not token:
                raise WechatApiError("wechat token response missing access_token")
            expires_in = max(int(payload.get("expires_in") or 7200), 300)
            _access_token = token
            _access_token_expires_at = time.monotonic() + expires_in - 120
            return token
        except httpx.HTTPError as exc:
            raise WechatApiError(f"wechat token request failed: {exc}") from exc
        finally:
            if owns_client:
                await http.aclose()


async def send_subscription_message(
    *,
    open_id: str,
    template_id: str,
    page: str,
    data: dict[str, dict[str, str]],
    client: httpx.AsyncClient | None = None,
) -> None:
    if not template_id:
        raise WechatApiError("wechat price alert template is not configured")
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=settings.wechat_request_timeout_seconds)
    try:
        for attempt in range(2):
            token = await _fetch_access_token(client=http, force=attempt > 0)
            response = await http.post(
                (
                    f"{settings.wechat_api_base_url.rstrip('/')}"
                    "/cgi-bin/message/subscribe/send"
                ),
                params={"access_token": token},
                json={
                    "touser": open_id,
                    "template_id": template_id,
                    "page": page,
                    "data": data,
                    "miniprogram_state": "formal",
                    "lang": "zh_CN",
                },
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            errcode = int(payload.get("errcode") or 0)
            if errcode == 0:
                return
            if errcode in {40001, 40014, 42001} and attempt == 0:
                continue
            raise WechatApiError(
                str(payload.get("errmsg") or "wechat message failed"),
                errcode=errcode,
            )
    except httpx.HTTPError as exc:
        raise WechatApiError(f"wechat message request failed: {exc}") from exc
    finally:
        if owns_client:
            await http.aclose()
