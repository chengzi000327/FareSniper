from __future__ import annotations

import asyncio
from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Thread
import time
from typing import Any, Iterator
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from backend.application.services.flight_query import build_flight_query
from backend.scripts import verify_live_fares as verifier


ROOT = Path(__file__).resolve().parents[3]
SECRET_JWT = "jwt-secret-sentinel"
SECRET_COLLECTOR = "collector-secret-sentinel"


def _run(
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "backend.scripts.verify_live_fares", *args],
        cwd=ROOT,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


@contextmanager
def _fake_backend(
    *,
    freshness: str = "fresh",
    statuses: tuple[str, ...] = ("completed", "leased", "completed"),
    query_overrides: dict[str, Any] | None = None,
    deal_overrides: dict[str, Any] | None = None,
    winner_overrides: dict[str, Any] | None = None,
    row_overrides: dict[str, Any] | None = None,
    duplicate_winner: bool = False,
    first_without_ctrip: bool = False,
    append_valid_deal: bool = False,
    analysis_min: int = 1688,
    recommendation_text: str = "平台展示价最低：¥1688。",
) -> Iterator[tuple[str, dict[str, Any]]]:
    state: dict[str, Any] = {
        "search_count": 0,
        "status_count": 0,
        "status_queries": [],
        "search_messages": [],
        "requests": [],
    }

    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            assert self.headers["Authorization"] == f"Bearer {SECRET_COLLECTOR}"
            assert self.path.startswith("/internal/collector/status?")
            status_query = parse_qs(urlsplit(self.path).query)
            state["status_queries"].append(status_query)
            state["requests"].append("status")
            status_index = min(state["status_count"], len(statuses) - 1)
            job_status = statuses[status_index]
            state["status_count"] += 1
            is_new_attempt = status_index > 0 and job_status in {
                "leased",
                "completed",
            }
            observed_minute = status_index if (
                is_new_attempt and job_status == "completed"
            ) else 0
            self._json(
                200,
                {
                    "collector_online": True,
                    "last_heartbeat_at": "2099-07-19T12:00:00Z",
                    "last_success_at": "2099-07-19T12:00:00Z",
                    "job_status": job_status,
                    "job_attempts": 2 if is_new_attempt else 1,
                    "job_updated_at": (
                        f"2099-07-19T12:{status_index:02d}:00Z"
                    ),
                    "snapshot_observed_at": (
                        f"2099-07-19T12:{observed_minute:02d}:00Z"
                    ),
                },
            )

        def do_POST(self) -> None:  # noqa: N802
            assert self.headers["Authorization"] == f"Bearer {SECRET_JWT}"
            assert self.path == "/api/search"
            state["requests"].append("search")
            state["search_count"] += 1
            length = int(self.headers.get("Content-Length", "0"))
            request_payload = json.loads(self.rfile.read(length))
            state["search_messages"].append(request_payload["message"])

            query = {
                "origin_code": "AAT",
                "destination_code": "SYX",
                "date_start": "2099-08-01",
            }
            query.update(query_overrides or {})
            winner = {
                "id": "flyai-winning-row",
                "data_provider": "flyai",
                "name": "飞猪",
                "price": 1688,
                "currency": "CNY",
                "url": "https://market.m.taobao.com/app/trip/flight-search/pages/index",
                "provider_status": "success",
                "price_status": "priced",
                "data_freshness": "fresh",
                "lowest": True,
            }
            winner.update(winner_overrides or {})
            row = {
                "id": "ctrip-proof-row",
                "data_provider": "ctrip_snapshot",
                "name": "携程",
                "price": 1999,
                "currency": "CNY",
                "url": "https://flights.ctrip.com/booking/CZ5704",
                "provider_status": (
                    "success" if freshness == "fresh" else "stale"
                ),
                "data_freshness": freshness,
            }
            row.update(row_overrides or {})
            pristine_deal = {
                "flight_no": "CZ5704",
                "origin_code": "AAT",
                "origin_airport_code": "AAT",
                "destination_code": "SYX",
                "destination_airport_code": "SYX",
                "depart_date": "2099-08-01",
                "winning_price_id": "flyai-winning-row",
                "price": 1688,
                "lowest_price": 1688,
                "total_price": 1688,
                "currency": "CNY",
                "prices": [winner, row],
            }
            if duplicate_winner:
                pristine_deal["prices"].append(deepcopy(winner))
            deal = deepcopy(pristine_deal)
            if first_without_ctrip:
                deal["prices"] = [deepcopy(winner)]
            deal.update(deal_overrides or {})
            deals = [deal]
            if append_valid_deal:
                deals.append(pristine_deal)
            self._json(
                200,
                {
                    "query": query,
                    "deals": deals,
                    "analysis": {"min_price": analysis_min},
                    "recommendation": {"text": recommendation_text},
                },
            )

        def log_message(self, _format: str, *args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def _live_args(
    base_url: str,
    *,
    timeout: str = "2",
    origin: str = "阿勒泰",
    destination: str = "三亚",
) -> tuple[str, ...]:
    return (
        "--base-url",
        base_url,
        "--origin",
        origin,
        "--destination",
        destination,
        "--depart-date",
        "2099-08-01",
        "--timeout-seconds",
        timeout,
        "--poll-seconds",
        "0.05",
        "--require-fresh",
    )


def _secret_env() -> dict[str, str]:
    return {
        "FARESNIPER_VERIFY_JWT": SECRET_JWT,
        "CTRIP_COLLECTOR_TOKEN": SECRET_COLLECTOR,
    }


def test_live_verifier_has_bounded_safe_cli_contract():
    result = _run("--help")

    assert result.returncode == 0
    assert "--origin" in result.stdout
    assert "--destination" in result.stdout
    assert "--depart-date" in result.stdout
    assert "--timeout-seconds" in result.stdout
    assert "--require-fresh" in result.stdout
    assert "API_KEY" not in result.stdout
    assert "CTRIP_COLLECTOR_TOKEN" not in result.stdout


def test_live_verifier_rejects_past_date_before_network_access():
    result = _run(
        "--origin",
        "阿勒泰",
        "--destination",
        "三亚",
        "--depart-date",
        "2000-01-01",
        env={
            "FARESNIPER_API_URL": "https://backend.example.test",
            "FARESNIPER_VERIFY_JWT": "must-not-appear",
            "CTRIP_COLLECTOR_TOKEN": "must-not-appear",
        },
    )

    assert result.returncode == 2
    combined = result.stdout + result.stderr
    assert "未来日期" in combined
    assert "must-not-appear" not in combined


def test_live_verifier_searches_only_to_trigger_and_verify_after_polling():
    statuses = ("pending", "pending", "pending", "completed")
    with _fake_backend(statuses=statuses) as (base_url, state):
        result = _run(*_live_args(base_url), env=_secret_env())

    assert result.returncode == 0, result.stderr
    assert state["search_count"] == 2
    assert state["requests"] == [
        "status",
        "search",
        "status",
        "status",
        "status",
        "search",
    ]
    assert all(
        query.get("origin_airport_code") == ["AAT"]
        and query.get("destination_airport_code") == ["SYX"]
        for query in state["status_queries"]
    )
    assert "collector=online" in result.stdout
    assert "job=completed" in result.stdout
    assert "ctrip_price=CNY 1999" in result.stdout
    assert SECRET_JWT not in result.stdout + result.stderr
    assert SECRET_COLLECTOR not in result.stdout + result.stderr
    assert "https://flights.ctrip.com" not in result.stdout


def test_live_verifier_trigger_preserves_explicit_multi_airport_scope():
    with _fake_backend(
        query_overrides={"origin_code": "BJS"},
        deal_overrides={
            "origin_code": "BJS",
            "origin_airport_code": "PKX",
        },
    ) as (base_url, state):
        result = _run(
            *_live_args(base_url, origin="北京大兴机场"),
            env=_secret_env(),
        )

    assert result.returncode == 0, result.stderr
    assert state["search_messages"]
    assert all("PKX" in message for message in state["search_messages"])
    assert all("北京到" not in message for message in state["search_messages"])
    assert all(
        query.get("origin_airport_code") == ["PKX"]
        for query in state["status_queries"]
    )


def test_live_verifier_rejects_unchanged_completed_job_and_snapshot():
    with _fake_backend(statuses=("completed",)) as (base_url, state):
        result = _run(
            *_live_args(base_url, timeout="1"), env=_secret_env()
        )

    assert result.returncode == 1
    assert "verification timed out" in result.stderr
    assert state["search_count"] == 1


def test_live_verifier_accepts_real_renderer_single_cny_amount_format():
    with _fake_backend(
        recommendation_text="平台展示价最低：¥1688。"
    ) as (base_url, state):
        result = _run(*_live_args(base_url), env=_secret_env())

    assert result.returncode == 0, result.stderr
    assert state["search_count"] == 2


def test_live_verifier_accepts_flyai_winner_and_higher_ctrip_proof_price():
    with _fake_backend() as (base_url, state):
        result = _run(*_live_args(base_url), env=_secret_env())

    assert result.returncode == 0, result.stderr
    assert "ctrip_price=CNY 1999" in result.stdout
    assert state["search_count"] == 2


def test_live_verifier_require_fresh_rejects_after_one_final_search():
    with _fake_backend(freshness="stale") as (base_url, state):
        result = _run(*_live_args(base_url, timeout="1"), env=_secret_env())

    assert result.returncode == 1
    assert "fresh Ctrip price not observed" in result.stderr
    assert state["search_count"] == 2
    assert SECRET_JWT not in result.stdout + result.stderr
    assert SECRET_COLLECTOR not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("backend_options", "expected_error"),
    [
        (
            {"query_overrides": {"destination_code": "HAK"}},
            "search response query does not match request",
        ),
        (
            {"deal_overrides": {"origin_code": "HAK"}},
            "first displayed card does not match request",
        ),
        (
            {"deal_overrides": {"depart_date": "2099-08-02"}},
            "first displayed card does not match request",
        ),
        (
            {"analysis_min": 1699},
            "first displayed card price does not match winner",
        ),
        (
            {"recommendation_text": "平台展示价最低：¥1699。"},
            "recommendation price does not match displayed card",
        ),
        (
            {"deal_overrides": {"winning_price_id": None}},
            "first displayed card has invalid winning row",
        ),
        (
            {"deal_overrides": {"winning_price_id": ""}},
            "first displayed card has invalid winning row",
        ),
        (
            {"deal_overrides": {"winning_price_id": "missing-row"}},
            "first displayed card has invalid winning row",
        ),
        (
            {"duplicate_winner": True},
            "first displayed card has invalid winning row",
        ),
        (
            {"winner_overrides": {"price": 1700}},
            "first displayed card price does not match winner",
        ),
        (
            {"deal_overrides": {"lowest_price": 1700}},
            "first displayed card price does not match winner",
        ),
        (
            {"deal_overrides": {"total_price": 1700}},
            "first displayed card price does not match winner",
        ),
        (
            {
                "deal_overrides": {"currency": "USD"},
                "recommendation_text": "平台展示价最低：USD 1688。",
            },
            "first displayed card currency does not match winner",
        ),
        (
            {"winner_overrides": {"currency": "USD"}},
            "first displayed card currency does not match winner",
        ),
        (
            {"row_overrides": {"currency": ""}},
            "scoped Ctrip price not observed",
        ),
    ],
)
def test_live_verifier_rejects_query_scope_card_and_text_mismatches(
    backend_options: dict[str, Any],
    expected_error: str,
):
    with _fake_backend(**backend_options) as (base_url, state):
        result = _run(*_live_args(base_url), env=_secret_env())

    assert result.returncode == 1
    assert expected_error in result.stderr
    assert state["search_count"] == 2


def test_live_verifier_rejects_nested_price_without_first_card_headline():
    with _fake_backend(
        deal_overrides={
            "price": None,
            "lowest_price": None,
            "total_price": None,
        },
        row_overrides={"price": 1688},
    ) as (base_url, state):
        result = _run(*_live_args(base_url), env=_secret_env())

    assert result.returncode == 1
    assert "first displayed card price does not match winner" in result.stderr
    assert state["search_count"] == 2


def test_live_verifier_rejects_later_match_when_first_card_scope_is_wrong():
    with _fake_backend(
        deal_overrides={"origin_code": "HAK"},
        first_without_ctrip=True,
        append_valid_deal=True,
    ) as (base_url, state):
        result = _run(*_live_args(base_url), env=_secret_env())

    assert result.returncode == 1
    assert "first displayed card does not match request" in result.stderr
    assert state["search_count"] == 2


def test_live_verifier_accepts_ctrip_proof_on_later_scoped_deal():
    with _fake_backend(
        first_without_ctrip=True,
        append_valid_deal=True,
    ) as (base_url, state):
        result = _run(*_live_args(base_url), env=_secret_env())

    assert result.returncode == 0, result.stderr
    assert "ctrip_price=CNY 1999" in result.stdout
    assert state["search_count"] == 2


@pytest.mark.asyncio
async def test_verify_enforces_one_wall_clock_deadline_and_remaining_request_budget():
    request_timeouts: list[float] = []

    async def slow_handler(request: httpx.Request) -> httpx.Response:
        request_timeouts.append(float(request.extensions["timeout"]["read"]))
        await asyncio.sleep(0.04)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "collector_online": True,
                    "job_status": "pending",
                    "job_attempts": 0,
                    "job_updated_at": None,
                    "snapshot_observed_at": None,
                },
            )
        return httpx.Response(200, json={})

    started = time.monotonic()
    with pytest.raises(verifier.VerificationError, match="verification timed out"):
        await verifier.verify(
            base_url="https://backend.example.test",
            query=build_flight_query("阿勒泰", "三亚", "2099-08-01"),
            jwt_token=SECRET_JWT,
            collector_token=SECRET_COLLECTOR,
            timeout_seconds=0.07,
            poll_seconds=0.01,
            require_fresh=True,
            transport=httpx.MockTransport(slow_handler),
        )
    elapsed = time.monotonic() - started

    assert elapsed < 0.2
    assert len(request_timeouts) == 2
    assert 0 < request_timeouts[1] < request_timeouts[0] <= 0.07
