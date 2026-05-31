from fastapi.testclient import TestClient

from backend.main import app


def test_health_reports_all_subsystems(seeded_pg, fake_redis):
    with TestClient(app) as c:
        r = c.get("/health")
        body = r.json()
        for k in [
            "graph_compiled",
            "redis_ok",
            "postgres_ok",
            "scheduler_ok",
            "langsmith_ok",
        ]:
            assert k in body, f"missing key: {k}"
