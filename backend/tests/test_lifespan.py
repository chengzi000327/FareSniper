"""TG-05 · Task 1 contract: lifespan compiles the graph and verifies Redis."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


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
