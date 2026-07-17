"""TG-05 · Task 1 contract: lifespan compiles the graph and verifies Redis."""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from backend.main import app, create_app


def test_health_reports_graph_compiled_and_redis_ok():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["graph_compiled"] is True
        assert body["redis_ok"] is True
        assert body["app"] == "FareSniper"


def test_health_works_without_lifespan_context_with_safe_defaults():
    """Hitting /health before/after lifespan still returns valid JSON.

    TestClient outside ``with`` doesn't trigger lifespan; the app must
    still expose graph_compiled / redis_ok as bools so frontends never
    see a missing key.
    """
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["graph_compiled"], bool)
    assert isinstance(body["redis_ok"], bool)


def test_api_does_not_build_scheduler_when_disabled(monkeypatch):
    monkeypatch.setattr("backend.main.settings.run_scheduler_in_api", False)
    monkeypatch.setattr(
        "backend.main.build_scheduler",
        lambda: pytest.fail("API must not own browser scheduler when disabled"),
    )
    monkeypatch.setattr("backend.main.settings.database_url", "")
    monkeypatch.setattr("backend.main.settings.redis_url", "")

    test_app = create_app()
    with TestClient(test_app):
        assert test_app.state.scheduler is None


def test_api_starts_and_stops_scheduler_when_enabled(monkeypatch):
    scheduler = _FakeScheduler()
    monkeypatch.setattr("backend.main.settings.run_scheduler_in_api", True)
    monkeypatch.setattr("backend.main.build_scheduler", lambda: scheduler)
    monkeypatch.setattr("backend.main.settings.database_url", "")
    monkeypatch.setattr("backend.main.settings.redis_url", "")

    test_app = create_app()
    with TestClient(test_app):
        assert test_app.state.scheduler is scheduler
        assert scheduler.running is True

    assert scheduler.running is False
    assert scheduler.shutdown_wait is False


class _FakeScheduler:
    def __init__(self):
        self.running = False
        self.shutdown_wait = None

    def start(self):
        self.running = True

    def shutdown(self, *, wait):
        self.shutdown_wait = wait
        self.running = False
