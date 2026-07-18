from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.application.contracts.collector import CollectorErrorCode
from backend.collector.browser import (
    BATCH_SEARCH_INTERCEPT_SCRIPT,
    CaptureResult,
    CtripBrowser,
    build_chrome_options,
    build_search_url,
    detect_page_error,
)


def _job(**overrides):
    payload = {
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2099-08-08",
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_capture_result_normalizes_wire_style_error_code():
    result = CaptureResult(error_code="login_required")

    assert result.error_code is CollectorErrorCode.login_required


def test_browser_uses_dedicated_profile_and_no_proxy(tmp_path, monkeypatch):
    monkeypatch.setenv("NO_PROXY", "example.test")

    options = build_chrome_options(profile_dir=tmp_path, headless=False)

    assert f"--user-data-dir={tmp_path.resolve()}" in options.arguments
    assert "--no-proxy-server" in options.arguments
    assert all("--headless" not in arg for arg in options.arguments)
    assert set(os.environ["NO_PROXY"].split(",")) >= {
        "example.test",
        "127.0.0.1",
        "localhost",
    }


def test_browser_rejects_default_chrome_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    default_profile = (
        tmp_path / "Library/Application Support/Google/Chrome/Default"
    )

    with pytest.raises(ValueError, match="dedicated"):
        build_chrome_options(profile_dir=default_profile, headless=False)


def test_interceptor_does_not_fabricate_browser_identity():
    assert "batchSearch" in BATCH_SEARCH_INTERCEPT_SCRIPT
    assert "navigator.webdriver" not in BATCH_SEARCH_INTERCEPT_SCRIPT
    assert "AutomationControlled" not in BATCH_SEARCH_INTERCEPT_SCRIPT


@pytest.mark.parametrize(
    ("url", "title", "source", "expected"),
    [
        (
            "https://passport.ctrip.com/user/login",
            "携程登录",
            "",
            CollectorErrorCode.login_required,
        ),
        (
            "https://flights.ctrip.com/online/list",
            "安全验证",
            "请完成验证码",
            CollectorErrorCode.captcha_required,
        ),
        (
            "https://flights.ctrip.com/online/list",
            "机票",
            "航班列表",
            None,
        ),
    ],
)
def test_page_state_detection_is_explicit(url, title, source, expected):
    driver = SimpleNamespace(current_url=url, title=title, page_source=source)
    assert detect_page_error(driver) is expected


def test_hidden_script_words_do_not_trigger_captcha_status():
    driver = SimpleNamespace(
        current_url="https://flights.ctrip.com/online/list",
        title="机票",
        page_source="<script>const captchaHandler = true;</script>",
        find_element=lambda *_args: SimpleNamespace(text="航班列表"),
    )

    assert detect_page_error(driver) is None


def test_search_url_contains_only_route_and_future_date():
    assert build_search_url(_job()) == (
        "https://flights.ctrip.com/online/list/oneway-bjs-sha"
        "?depdate=2099-08-08"
    )


@pytest.mark.asyncio
async def test_login_is_visible_and_uses_dedicated_profile(tmp_path):
    calls: dict[str, object] = {}

    class Driver:
        def execute_cdp_cmd(self, *_args):
            pass

        def get(self, url):
            calls["url"] = url

        def quit(self):
            calls["quit"] = True

    def factory(*, options):
        calls["arguments"] = options.arguments
        return Driver()

    browser = CtripBrowser(profile_dir=tmp_path, driver_factory=factory)
    await browser.login(wait_for_user=lambda: calls.setdefault("waited", True))
    await browser.close()

    assert calls["url"] == "https://www.ctrip.com/"
    assert calls["waited"] is True
    assert all("--headless" not in arg for arg in calls["arguments"])
    assert f"--user-data-dir={tmp_path.resolve()}" in calls["arguments"]
    assert calls["quit"] is True


def test_captured_payloads_are_decoded_without_logging_raw_content():
    payload = {"data": {"flightItineraryList": []}}
    driver = SimpleNamespace(
        execute_script=lambda _script: json.dumps([json.dumps(payload)])
    )

    assert CtripBrowser._extract_payloads(driver) == [payload]
