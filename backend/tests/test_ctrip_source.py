from __future__ import annotations

import importlib.util

import pytest

from backend.application.contracts.collector import CollectorErrorCode
from backend.data_sources.ctrip_source import CtripCollectionError, CtripSource


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
async def test_search_flights_preserves_collection_failure(monkeypatch):
    async def parse_error_worker(self, *args):
        raise CtripCollectionError(CollectorErrorCode.parse_error)

    _install_selenium_marker(monkeypatch)
    monkeypatch.setattr(CtripSource, "_run_worker_once", parse_error_worker)

    with pytest.raises(CtripCollectionError) as exc_info:
        await CtripSource(enable_mock_fallback=True).search_flights(
            "BJS", "SHA", "2026-08-08", "2026-08-08"
        )

    assert exc_info.value.code is CollectorErrorCode.parse_error
