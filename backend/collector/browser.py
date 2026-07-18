from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from backend.application.contracts.collector import CollectorErrorCode


DEFAULT_PROFILE_DIR = Path.home() / ".faresniper" / "ctrip-profile"
CTRIP_HOME_URL = "https://www.ctrip.com/"
_ROUTE_CODE_PATTERN = re.compile(r"[A-Za-z]{3}\Z")
_AUTH_COOKIE_NAMES = frozenset({"cticket", "login_uid"})

BATCH_SEARCH_INTERCEPT_SCRIPT = """
(function() {
    window.__faresniperBatchSearchResponses = [];
    const originalFetch = window.fetch;
    window.fetch = function(input) {
        const requestUrl = typeof input === 'string'
            ? input : (input && input.url) || '';
        return originalFetch.apply(this, arguments).then(function(response) {
            if (requestUrl.indexOf('batchSearch') !== -1) {
                response.clone().text().then(function(body) {
                    window.__faresniperBatchSearchResponses.push(body);
                });
            }
            return response;
        });
    };
    const originalOpen = XMLHttpRequest.prototype.open;
    const originalSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(method, url) {
        this.__faresniperUrl = url;
        return originalOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function() {
        const request = this;
        if ((this.__faresniperUrl || '').indexOf('batchSearch') !== -1) {
            request.addEventListener('load', function() {
                try {
                    window.__faresniperBatchSearchResponses.push(
                        request.responseText
                    );
                } catch (ignored) {}
            });
        }
        return originalSend.apply(this, arguments);
    };
})();
"""


@dataclass(frozen=True)
class CaptureResult:
    payloads: list[dict[str, Any]] = field(default_factory=list)
    error_code: CollectorErrorCode | str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.error_code, str):
            object.__setattr__(
                self,
                "error_code",
                CollectorErrorCode(self.error_code),
            )


def _chrome_root() -> Path:
    return Path.home() / "Library/Application Support/Google/Chrome"


def _ensure_dedicated_profile(profile_dir: Path) -> Path:
    profile = profile_dir.expanduser().resolve()
    chrome_root = _chrome_root().expanduser().resolve()
    if profile == chrome_root or profile.is_relative_to(chrome_root):
        raise ValueError("collector requires a dedicated Chrome profile")
    profile.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        profile.chmod(0o700)
    except OSError:
        pass
    return profile


def _set_localhost_no_proxy() -> None:
    for name in ("NO_PROXY", "no_proxy"):
        values = [
            value.strip()
            for value in os.environ.get(name, "").split(",")
            if value.strip()
        ]
        for required in ("127.0.0.1", "localhost"):
            if required not in values:
                values.append(required)
        os.environ[name] = ",".join(values)


def build_chrome_options(*, profile_dir: Path, headless: bool):
    from selenium.webdriver.chrome.options import Options

    profile = _ensure_dedicated_profile(profile_dir)
    _set_localhost_no_proxy()
    options = Options()
    options.add_argument(f"--user-data-dir={profile}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--no-proxy-server")
    options.add_argument("--window-size=1440,1000")
    if headless:
        options.add_argument("--headless=new")
    return options


def build_search_url(job: object) -> str:
    origin = str(getattr(job, "origin_code", ""))
    destination = str(getattr(job, "destination_code", ""))
    depart_date = str(getattr(job, "depart_date", ""))
    if (
        _ROUTE_CODE_PATTERN.fullmatch(origin) is None
        or _ROUTE_CODE_PATTERN.fullmatch(destination) is None
    ):
        raise ValueError("collector route codes must be three ASCII letters")
    try:
        parsed_date = date.fromisoformat(depart_date)
    except ValueError as exc:
        raise ValueError("collector depart date is invalid") from exc
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    if parsed_date <= today:
        raise ValueError("collector depart date must be in the future")
    return (
        "https://flights.ctrip.com/online/list/oneway-"
        f"{origin.lower()}-{destination.lower()}?depdate={depart_date}"
    )


def detect_page_error(driver: object) -> CollectorErrorCode | None:
    current_url = str(getattr(driver, "current_url", "")).casefold()
    title = str(getattr(driver, "title", "")).casefold()
    find_element = getattr(driver, "find_element", None)
    if callable(find_element):
        try:
            visible_text = str(find_element("tag name", "body").text)
        except Exception:
            visible_text = ""
    else:
        visible_text = str(getattr(driver, "page_source", ""))
    combined = " ".join((current_url, title, visible_text.casefold()))
    captcha_markers = (
        "captcha",
        "验证码",
        "安全验证",
        "滑块验证",
    )
    if any(marker in combined for marker in captcha_markers):
        return CollectorErrorCode.captcha_required
    login_markers = (
        "passport.ctrip.com",
        "/user/login",
        "请先登录",
        "登录后查看",
    )
    if any(marker in combined for marker in login_markers):
        return CollectorErrorCode.login_required
    return None


class CtripBrowser:
    def __init__(
        self,
        *,
        profile_dir: Path = DEFAULT_PROFILE_DIR,
        timeout_seconds: float = 90.0,
        driver_factory: Callable[..., object] | None = None,
    ) -> None:
        self.profile_dir = _ensure_dedicated_profile(profile_dir)
        self.timeout_seconds = timeout_seconds
        self._driver_factory = driver_factory
        self._driver: object | None = None
        self._headless: bool | None = None

    async def login(
        self,
        *,
        wait_for_user: Callable[[], object] | None = None,
    ) -> CollectorErrorCode | None:
        waiter = wait_for_user or (
            lambda: input("请在 Chrome 中完成携程登录，然后按回车继续：")
        )
        return await asyncio.to_thread(self._login_sync, waiter)

    async def capture(self, job: object) -> CaptureResult:
        return await asyncio.to_thread(self._capture_sync, job)

    async def reset_session(self) -> None:
        await asyncio.to_thread(self._close_sync)

    async def close(self) -> None:
        await self.reset_session()

    def _create_driver(self, *, headless: bool) -> object:
        options = build_chrome_options(
            profile_dir=self.profile_dir,
            headless=headless,
        )
        if self._driver_factory is None:
            from selenium import webdriver

            driver = webdriver.Chrome(options=options)
        else:
            driver = self._driver_factory(options=options)
        execute_cdp = getattr(driver, "execute_cdp_cmd", None)
        if callable(execute_cdp):
            execute_cdp(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": BATCH_SEARCH_INTERCEPT_SCRIPT},
            )
        set_timeout = getattr(driver, "set_page_load_timeout", None)
        if callable(set_timeout):
            set_timeout(min(self.timeout_seconds, 30.0))
        return driver

    def _driver_for(self, *, headless: bool) -> object:
        if self._driver is not None and self._headless != headless:
            self._close_sync()
        if self._driver is None:
            self._driver = self._create_driver(headless=headless)
            self._headless = headless
        return self._driver

    def _login_sync(
        self,
        wait_for_user: Callable[[], object],
    ) -> CollectorErrorCode | None:
        try:
            driver = self._driver_for(headless=False)
            getattr(driver, "get")(CTRIP_HOME_URL)
            wait_for_user()
            probe_date = (
                datetime.now(ZoneInfo("Asia/Shanghai")).date()
                + timedelta(days=30)
            )
            probe_url = (
                "https://flights.ctrip.com/online/list/oneway-bjs-sha"
                f"?depdate={probe_date.isoformat()}"
            )
            getattr(driver, "get")(probe_url)
            page_error = detect_page_error(driver)
            if page_error is not None:
                return page_error
            if not self._has_authenticated_session(driver):
                return CollectorErrorCode.login_required
            return None
        except Exception as exc:
            if exc.__class__.__module__.startswith("selenium"):
                return CollectorErrorCode.dependency_error
            raise

    def _capture_sync(self, job: object) -> CaptureResult:
        try:
            driver = self._driver_for(headless=True)
            getattr(driver, "get")(build_search_url(job))
            deadline = time.monotonic() + self.timeout_seconds
            while time.monotonic() < deadline:
                page_error = detect_page_error(driver)
                if page_error is not None:
                    return self._capture_failure(page_error)
                ready = getattr(driver, "execute_script")(
                    "return !!(window.__faresniperBatchSearchResponses && "
                    "window.__faresniperBatchSearchResponses.length);"
                )
                if ready:
                    payloads = self._extract_payloads(driver)
                    if not payloads:
                        return self._capture_failure(
                            CollectorErrorCode.parse_error
                        )
                    return CaptureResult(payloads=payloads)
                time.sleep(0.25)
            return self._capture_failure(
                detect_page_error(driver) or CollectorErrorCode.timeout
            )
        except (ImportError, ModuleNotFoundError):
            return self._capture_failure(
                CollectorErrorCode.dependency_error
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return self._capture_failure(CollectorErrorCode.parse_error)
        except Exception:
            return self._capture_failure(
                CollectorErrorCode.dependency_error
            )

    @staticmethod
    def _has_authenticated_session(driver: object) -> bool:
        get_cookies = getattr(driver, "get_cookies", None)
        if not callable(get_cookies):
            return False
        try:
            cookies = get_cookies()
        except Exception:
            return False
        if not isinstance(cookies, list):
            return False
        now = time.time()
        for cookie in cookies:
            if not isinstance(cookie, Mapping):
                continue
            name = str(cookie.get("name", "")).casefold()
            if name not in _AUTH_COOKIE_NAMES or not cookie.get("value"):
                continue
            expiry = cookie.get("expiry")
            if isinstance(expiry, (int, float)) and expiry <= now:
                continue
            return True
        return False

    def _capture_failure(
        self,
        error_code: CollectorErrorCode,
    ) -> CaptureResult:
        self._close_sync()
        return CaptureResult(error_code=error_code)

    @staticmethod
    def _extract_payloads(driver: object) -> list[dict[str, Any]]:
        encoded = getattr(driver, "execute_script")(
            "const responses = "
            "window.__faresniperBatchSearchResponses || [];"
            "window.__faresniperBatchSearchResponses = [];"
            "return JSON.stringify(responses);"
        )
        bodies = json.loads(encoded) if isinstance(encoded, str) else encoded
        if not isinstance(bodies, list):
            raise ValueError("batchSearch capture is invalid")
        payloads: list[dict[str, Any]] = []
        for body in bodies:
            decoded = json.loads(body) if isinstance(body, str) else body
            if not isinstance(decoded, Mapping):
                raise ValueError("batchSearch response is invalid")
            payloads.append(dict(decoded))
        return payloads

    def _close_sync(self) -> None:
        driver, self._driver = self._driver, None
        self._headless = None
        if driver is None:
            return
        try:
            getattr(driver, "quit")()
        except Exception:
            pass
