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


class FakeOptions:
    def __init__(self):
        self.arguments: list[str] = []

    def add_argument(self, value: str) -> None:
        self.arguments.append(value)


def _options_factory() -> FakeOptions:
    return FakeOptions()


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


def test_browser_uses_dedicated_profile_and_ctrip_only_proxy_bypass(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("NO_PROXY", "example.test")

    options = build_chrome_options(
        profile_dir=tmp_path,
        headless=False,
        options_factory=_options_factory,
    )

    assert f"--user-data-dir={tmp_path.resolve()}" in options.arguments
    assert "--no-proxy-server" not in options.arguments
    assert (
        "--proxy-bypass-list=ctrip.com;*.ctrip.com;ctrip.com.cn;*.ctrip.com.cn"
        in options.arguments
    )
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
        build_chrome_options(
            profile_dir=default_profile,
            headless=False,
            options_factory=_options_factory,
        )


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


def test_search_url_prefers_explicit_airport_scope():
    assert build_search_url(
        _job(origin_airport_code="PKX", destination_airport_code="SHA")
    ) == (
        "https://flights.ctrip.com/online/list/oneway-pkx-sha"
        "?depdate=2099-08-08"
    )


@pytest.mark.asyncio
async def test_login_is_visible_and_uses_dedicated_profile(tmp_path):
    calls: dict[str, object] = {}

    class Driver:
        current_url = "https://www.ctrip.com/"
        title = "携程旅行"
        page_source = ""

        def execute_cdp_cmd(self, *_args):
            pass

        def get(self, url):
            calls.setdefault("urls", []).append(url)
            self.current_url = url

        def get_cookies(self):
            return [{"name": "cticket", "value": "opaque-session"}]

        def find_element(self, *_args):
            return SimpleNamespace(text="航班列表")

        def quit(self):
            calls["quit"] = True

    def factory(*, options):
        calls["arguments"] = options.arguments
        return Driver()

    browser = CtripBrowser(
        profile_dir=tmp_path,
        driver_factory=factory,
        options_factory=_options_factory,
    )
    await browser.login(wait_for_user=lambda: calls.setdefault("waited", True))
    await browser.close()

    assert calls["urls"][0] == "https://www.ctrip.com/"
    assert "flights.ctrip.com/online/list/oneway-bjs-sha" in calls["urls"][1]
    assert calls["waited"] is True
    assert all("--headless" not in arg for arg in calls["arguments"])
    assert f"--user-data-dir={tmp_path.resolve()}" in calls["arguments"]
    assert calls["quit"] is True


@pytest.mark.asyncio
async def test_capture_uses_configured_headed_browser_mode(tmp_path):
    calls: dict[str, object] = {}

    class Driver:
        current_url = "https://flights.ctrip.com/online/list"
        title = "机票"
        page_source = ""

        def execute_cdp_cmd(self, *_args):
            pass

        def get(self, url):
            self.current_url = url

        def find_element(self, *_args):
            return SimpleNamespace(text="航班列表")

        def execute_script(self, script):
            if script.startswith("return !!"):
                return True
            return json.dumps(
                [json.dumps({"data": {"flightItineraryList": []}})]
            )

        def quit(self):
            pass

    def factory(*, options):
        calls["arguments"] = options.arguments
        return Driver()

    browser = CtripBrowser(
        profile_dir=tmp_path,
        headless=False,
        driver_factory=factory,
        options_factory=_options_factory,
    )
    try:
        result = await browser.capture(_job())
    finally:
        await browser.close()

    assert result.error_code is None
    assert all("--headless" not in arg for arg in calls["arguments"])


@pytest.mark.asyncio
async def test_generic_logged_out_homepage_is_not_authenticated(tmp_path):
    class Driver:
        current_url = "https://www.ctrip.com/"
        title = "携程旅行"
        page_source = ""

        def execute_cdp_cmd(self, *_args):
            pass

        def get(self, url):
            self.current_url = url

        def get_cookies(self):
            return [{"name": "anonymous-id", "value": "not-auth"}]

        def find_element(self, *_args):
            return SimpleNamespace(text="航班列表")

        def quit(self):
            pass

    browser = CtripBrowser(
        profile_dir=tmp_path,
        driver_factory=lambda **_kwargs: Driver(),
        options_factory=_options_factory,
    )
    try:
        status = await browser.login(wait_for_user=lambda: None)
    finally:
        await browser.close()

    assert status is CollectorErrorCode.login_required


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_url", "failure_title", "expected"),
    [
        (
            "https://passport.ctrip.com/user/login",
            "携程登录",
            CollectorErrorCode.login_required,
        ),
        (
            "https://flights.ctrip.com/online/list",
            "安全验证",
            CollectorErrorCode.captcha_required,
        ),
    ],
)
async def test_capture_page_failure_releases_profile_and_recreates_driver(
    tmp_path,
    failure_url,
    failure_title,
    expected,
):
    drivers = []

    class Driver:
        page_source = ""

        def __init__(self, number):
            self.number = number
            self.current_url = ""
            self.title = ""
            self.quit_calls = 0

        def execute_cdp_cmd(self, *_args):
            pass

        def get(self, url):
            if self.number == 1:
                self.current_url = failure_url
                self.title = failure_title
            else:
                self.current_url = url
                self.title = "机票"

        def find_element(self, *_args):
            return SimpleNamespace(text=self.title)

        def execute_script(self, script):
            if script.startswith("return !!"):
                return True
            return json.dumps(
                [json.dumps({"data": {"flightItineraryList": []}})]
            )

        def quit(self):
            self.quit_calls += 1

    def factory(**_kwargs):
        driver = Driver(len(drivers) + 1)
        drivers.append(driver)
        return driver

    browser = CtripBrowser(
        profile_dir=tmp_path,
        driver_factory=factory,
        options_factory=_options_factory,
    )
    first = await browser.capture(_job())
    second = await browser.capture(_job())
    await browser.close()

    assert first.error_code is expected
    assert len(drivers) == 2
    assert drivers[0].quit_calls == 1
    assert second.error_code is None


@pytest.mark.asyncio
async def test_capture_dependency_failure_releases_cached_driver(tmp_path):
    drivers = []

    class Driver:
        def __init__(self, should_fail):
            self.should_fail = should_fail
            self.current_url = ""
            self.title = ""
            self.page_source = ""
            self.quit_calls = 0

        def execute_cdp_cmd(self, *_args):
            pass

        def get(self, url):
            if self.should_fail:
                raise RuntimeError("browser session failed")
            self.current_url = "https://passport.ctrip.com/user/login"

        def find_element(self, *_args):
            return SimpleNamespace(text="请先登录")

        def quit(self):
            self.quit_calls += 1

    def factory(**_kwargs):
        driver = Driver(should_fail=not drivers)
        drivers.append(driver)
        return driver

    browser = CtripBrowser(
        profile_dir=tmp_path,
        driver_factory=factory,
        options_factory=_options_factory,
    )
    first = await browser.capture(_job())
    second = await browser.capture(_job())
    await browser.close()

    assert first.error_code is CollectorErrorCode.dependency_error
    assert len(drivers) == 2
    assert drivers[0].quit_calls == 1
    assert second.error_code is CollectorErrorCode.login_required


def test_captured_payloads_are_decoded_without_logging_raw_content():
    payload = {"data": {"flightItineraryList": []}}
    driver = SimpleNamespace(
        execute_script=lambda _script: json.dumps([json.dumps(payload)])
    )

    assert CtripBrowser._extract_payloads(driver) == [payload]
