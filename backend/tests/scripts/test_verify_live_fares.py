from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from typing import Iterator


ROOT = Path(__file__).resolve().parents[3]
SECRET_JWT = "jwt-secret-sentinel"
SECRET_COLLECTOR = "collector-secret-sentinel"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
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
def _fake_backend(*, freshness: str = "fresh") -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            assert self.headers["Authorization"] == f"Bearer {SECRET_COLLECTOR}"
            assert self.path.startswith("/internal/collector/status?")
            self._json(
                200,
                {
                    "collector_online": True,
                    "last_heartbeat_at": "2099-07-19T12:00:00Z",
                    "last_success_at": "2099-07-19T12:00:00Z",
                    "job_status": "completed",
                    "job_updated_at": "2099-07-19T12:00:00Z",
                },
            )

        def do_POST(self) -> None:  # noqa: N802
            assert self.headers["Authorization"] == f"Bearer {SECRET_JWT}"
            assert self.path == "/api/search"
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            assert "阿勒泰" in payload["message"]
            assert "三亚" in payload["message"]
            self._json(
                200,
                {
                    "deals": [
                        {
                            "flight_no": "CZ5704",
                            "price": None,
                            "currency": "CNY",
                            "prices": [
                                {
                                    "data_provider": "ctrip_snapshot",
                                    "name": "携程",
                                    "price": 1688,
                                    "currency": "CNY",
                                    "url": "https://flights.ctrip.com/booking/CZ5704",
                                    "provider_status": (
                                        "success" if freshness == "fresh" else "stale"
                                    ),
                                    "data_freshness": freshness,
                                }
                            ],
                        }
                    ],
                    "analysis": {"min_price": 1688},
                    "recommendation": {
                        "text": "平台展示价最低：¥1688（CNY 1688）。"
                    },
                },
            )

        def log_message(self, _format: str, *args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


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


def test_live_verifier_accepts_fresh_ctrip_price_and_grounded_response():
    with _fake_backend() as base_url:
        result = _run(
            "--base-url",
            base_url,
            "--origin",
            "阿勒泰",
            "--destination",
            "三亚",
            "--depart-date",
            "2099-08-01",
            "--timeout-seconds",
            "2",
            "--poll-seconds",
            "0.05",
            "--require-fresh",
            env={
                "FARESNIPER_VERIFY_JWT": SECRET_JWT,
                "CTRIP_COLLECTOR_TOKEN": SECRET_COLLECTOR,
            },
        )

    assert result.returncode == 0, result.stderr
    assert "collector=online" in result.stdout
    assert "job=completed" in result.stdout
    assert "ctrip_price=CNY 1688" in result.stdout
    for trace_name in (
        "ctrip_collector_claim",
        "ctrip_local_collect",
        "ctrip_collector_ingest",
        "flight_search",
    ):
        assert trace_name in result.stdout
    assert SECRET_JWT not in result.stdout + result.stderr
    assert SECRET_COLLECTOR not in result.stdout + result.stderr
    assert "https://flights.ctrip.com" not in result.stdout


def test_live_verifier_require_fresh_rejects_stale_only_ctrip_result():
    with _fake_backend(freshness="stale") as base_url:
        result = _run(
            "--base-url",
            base_url,
            "--origin",
            "阿勒泰",
            "--destination",
            "三亚",
            "--depart-date",
            "2099-08-01",
            "--timeout-seconds",
            "1",
            "--poll-seconds",
            "0.05",
            "--require-fresh",
            env={
                "FARESNIPER_VERIFY_JWT": SECRET_JWT,
                "CTRIP_COLLECTOR_TOKEN": SECRET_COLLECTOR,
            },
        )

    assert result.returncode == 1
    assert "fresh Ctrip price not observed" in result.stderr
    assert SECRET_JWT not in result.stdout + result.stderr
    assert SECRET_COLLECTOR not in result.stdout + result.stderr
