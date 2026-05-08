from __future__ import annotations

import httpx

from backend.config import settings


async def send_sms(phone: str, text: str) -> None:
    """Route to SMS provider based on settings.sms_provider.

    Tests replace this via monkeypatch (fake_sms fixture) to capture OTP codes.
    """
    if settings.sms_provider == "aliyun":
        async with httpx.AsyncClient(timeout=5) as c:
            await c.post(
                settings.sms_aliyun_endpoint,
                json={
                    "PhoneNumbers": phone,
                    "TemplateParam": {"text": text},
                    "AccessKeyId": settings.sms_aliyun_access_key_id,
                },
            )
    elif settings.sms_provider == "twilio":
        async with httpx.AsyncClient(
            timeout=5, auth=(settings.sms_twilio_sid, settings.sms_twilio_token)
        ) as c:
            await c.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{settings.sms_twilio_sid}/Messages.json",
                data={"To": phone, "From": settings.sms_twilio_from, "Body": text},
            )
    else:
        raise RuntimeError(f"unsupported SMS_PROVIDER={settings.sms_provider!r}")
