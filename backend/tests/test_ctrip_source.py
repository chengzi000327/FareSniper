from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from backend.application.contracts.collector import CollectorErrorCode
from backend.data_sources.ctrip_source import CtripCollectionError, CtripSource


class _FakeWebDriverException(Exception):
    pass


class _FakeTimeoutException(_FakeWebDriverException):
    pass


class _ImmediateWait:
    def __init__(self, driver, timeout):
        self.driver = driver

    def until(self, predicate):
        return predicate(self.driver)


class _CtripDriver:
    def __init__(
        self,
        *,
        get_error=None,
        raw_responses="[]",
        current_url="https://flights.ctrip.com/online/list/oneway-bjs-sha",
        title="Flights",
        page_source="",
    ):
        self.get_error = get_error
        self.raw_responses = raw_responses
        self.current_url = current_url
        self.title = title
        self.page_source = page_source

    def get(self, url):
        if self.get_error is not None:
            raise self.get_error

    def execute_script(self, script):
        if script.startswith("var r = window.__flightResponses"):
            return self.raw_responses
        return True


def _module(name: str, **attributes) -> ModuleType:
    module = ModuleType(name)
    for attribute, value in attributes.items():
        setattr(module, attribute, value)
    return module


def _load_ctrip_api(monkeypatch):
    stubs = {
        "selenium": _module("selenium"),
        "selenium.webdriver": _module("selenium.webdriver"),
        "selenium.webdriver.support": _module("selenium.webdriver.support"),
        "selenium.webdriver.support.ui": _module(
            "selenium.webdriver.support.ui", WebDriverWait=_ImmediateWait
        ),
        "selenium.common": _module("selenium.common"),
        "selenium.common.exceptions": _module(
            "selenium.common.exceptions",
            TimeoutException=_FakeTimeoutException,
            WebDriverException=_FakeWebDriverException,
        ),
        "config": _module("config", REQUEST_DELAY=0),
        "shared": _module("shared", parse_datetime=lambda value: None),
        "browser": _module(
            "browser",
            init_browser=lambda **kwargs: (None, None),
            close_browser=lambda driver, profile: None,
            BATCH_INTERCEPT_JS="",
        ),
    }
    for name, module in stubs.items():
        monkeypatch.setitem(sys.modules, name, module)

    module_path = (
        Path(__file__).parents[1]
        / "third_party"
        / "flights_monitor"
        / "ctrip_api.py"
    )
    spec = importlib.util.spec_from_file_location("_test_ctrip_api", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    return module


def _search_batch(client):
    return client.search_batch_search(
        "BJS", "SHA", "北京", "上海", "2026-08-08"
    )


def test_navigation_failure_is_dependency_error(monkeypatch):
    ctrip_api = _load_ctrip_api(monkeypatch)
    client = ctrip_api.CtripFlightClient(headless=True)
    client.driver = _CtripDriver(get_error=ctrip_api.WebDriverException())

    with pytest.raises(ctrip_api.CtripBrowserError) as exc_info:
        _search_batch(client)

    assert exc_info.value.code == "dependency_error"


def test_navigation_timeout_is_timeout(monkeypatch):
    ctrip_api = _load_ctrip_api(monkeypatch)
    client = ctrip_api.CtripFlightClient(headless=True)
    client.driver = _CtripDriver(get_error=ctrip_api.TimeoutException())

    with pytest.raises(ctrip_api.CtripBrowserError) as exc_info:
        _search_batch(client)

    assert exc_info.value.code == "timeout"


def test_navigation_timeout_on_login_page_is_login_required(monkeypatch):
    ctrip_api = _load_ctrip_api(monkeypatch)
    client = ctrip_api.CtripFlightClient(headless=True)
    client.driver = _CtripDriver(
        get_error=ctrip_api.TimeoutException(),
        current_url="https://passport.ctrip.com/user/login",
        title="Login",
    )

    with pytest.raises(ctrip_api.CtripBrowserError) as exc_info:
        _search_batch(client)

    assert exc_info.value.code == "login_required"


def test_malformed_intercepted_payload_is_parse_error(monkeypatch):
    ctrip_api = _load_ctrip_api(monkeypatch)
    client = ctrip_api.CtripFlightClient(headless=True)
    client.driver = _CtripDriver(raw_responses="{not-json")

    with pytest.raises(ctrip_api.CtripBrowserError) as exc_info:
        _search_batch(client)

    assert exc_info.value.code == "parse_error"


def test_module_worker_resolves_vendored_imports_and_emits_json(tmp_path):
    backend_dir = tmp_path / "backend"
    worker_dir = backend_dir / "data_sources"
    contracts_dir = backend_dir / "application" / "contracts"
    vendored_dir = backend_dir / "third_party" / "flights_monitor"
    for package_dir in (
        backend_dir,
        worker_dir,
        backend_dir / "application",
        contracts_dir,
        backend_dir / "third_party",
        vendored_dir,
    ):
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

    worker_source = (
        Path(__file__).parents[1] / "data_sources" / "ctrip_browser_worker.py"
    )
    shutil.copyfile(worker_source, worker_dir / "ctrip_browser_worker.py")
    (contracts_dir / "collector.py").write_text(
        """from enum import Enum

class CollectorErrorCode(str, Enum):
    dependency_error = "dependency_error"
    login_required = "login_required"
    captcha_required = "captcha_required"
    timeout = "timeout"
    empty = "empty"
    parse_error = "parse_error"
""",
        encoding="utf-8",
    )
    (vendored_dir / "ctrip_api.py").write_text(
        """class CtripBrowserError(RuntimeError):
    def __init__(self, code):
        self.code = code

class CtripFlightClient:
    def __init__(self, *, headless):
        self.headless = headless

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def search_batch_search(self, **kwargs):
        return [{"code": 0, "data": {"source": "vendored"}}]
""",
        encoding="utf-8",
    )
    (vendored_dir / "shared.py").write_text(
        "def resolve_city(code):\n    return code\n", encoding="utf-8"
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.data_sources.ctrip_browser_worker",
            "--origin",
            "BJS",
            "--destination",
            "SHA",
            "--date-start",
            "2026-08-08",
            "--date-end",
            "2026-08-08",
            "--headless",
        ],
        cwd=tmp_path,
        env={
            key: os.environ[key]
            for key in ("PATH", "HOME", "TMPDIR", "LANG")
            if key in os.environ
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "ok": True,
        "payloads": [
            {
                "depart_date": "2026-08-08",
                "payload": {"code": 0, "data": {"source": "vendored"}},
            }
        ],
    }


def _install_selenium_marker(monkeypatch) -> None:
    original_find_spec = importlib.util.find_spec

    def available_selenium(name: str, *args, **kwargs):
        if name == "selenium":
            return object()
        return original_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", available_selenium)


@pytest.mark.asyncio
async def test_missing_selenium_is_dependency_error(monkeypatch):
    original_find_spec = importlib.util.find_spec

    def missing_selenium(name: str, *args, **kwargs):
        if name == "selenium":
            return None
        return original_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", missing_selenium)

    result = await CtripSource(enable_mock_fallback=False).search_with_status(
        "BJS", "SHA", "2026-08-08", "2026-08-08"
    )

    assert result.offers == []
    assert result.error_code is CollectorErrorCode.dependency_error


@pytest.mark.asyncio
async def test_worker_captcha_is_explicit_status(monkeypatch):
    async def captcha_worker(self, *args):
        raise CtripCollectionError(CollectorErrorCode.captcha_required)

    _install_selenium_marker(monkeypatch)
    monkeypatch.setattr(CtripSource, "_run_worker_once", captcha_worker)

    result = await CtripSource().search_with_status(
        "BJS", "SHA", "2026-08-08", "2026-08-08"
    )

    assert result.offers == []
    assert result.error_code is CollectorErrorCode.captcha_required


@pytest.mark.asyncio
async def test_valid_empty_worker_response_is_not_success(monkeypatch):
    async def empty_worker(self, *args):
        return []

    _install_selenium_marker(monkeypatch)
    monkeypatch.setattr(CtripSource, "_run_worker_once", empty_worker)

    result = await CtripSource().search_with_status(
        "BJS", "SHA", "2026-08-08", "2026-08-08"
    )

    assert result.offers == []
    assert result.error_code is CollectorErrorCode.empty


@pytest.mark.asyncio
async def test_search_flights_returns_offers_while_status_preserves_failure(
    monkeypatch,
):
    async def parse_error_worker(self, *args):
        raise CtripCollectionError(CollectorErrorCode.parse_error)

    _install_selenium_marker(monkeypatch)
    monkeypatch.setattr(CtripSource, "_run_worker_once", parse_error_worker)
    source = CtripSource(enable_mock_fallback=True)

    offers = await source.search_flights(
        "BJS", "SHA", "2026-08-08", "2026-08-08"
    )
    result = await source.search_with_status(
        "BJS", "SHA", "2026-08-08", "2026-08-08"
    )

    assert offers == []
    assert result.error_code is CollectorErrorCode.parse_error
