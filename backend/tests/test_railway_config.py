import pathlib
import tomllib


def test_railway_has_three_services():
    cfg = tomllib.loads(pathlib.Path("railway.toml").read_text())
    services = {s["name"] for s in cfg.get("services", [])}
    assert {"backend", "worker", "frontend"}.issubset(services)


def test_railway_backend_migrates_before_start_and_worker_command_is_stable():
    cfg = tomllib.loads(pathlib.Path("railway.toml").read_text())
    services = {service["name"]: service for service in cfg["services"]}

    assert services["backend"]["startCommand"] == (
        "alembic -c backend/alembic.ini upgrade head && "
        "uvicorn backend.main:app --host 0.0.0.0 --port $PORT"
    )
    assert services["worker"]["startCommand"] == (
        "python -m backend.workers.run_all"
    )
