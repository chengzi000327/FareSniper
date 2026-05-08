import pathlib
import tomllib


def test_railway_has_three_services():
    cfg = tomllib.loads(pathlib.Path("railway.toml").read_text())
    services = {s["name"] for s in cfg.get("services", [])}
    assert {"backend", "worker", "frontend"}.issubset(services)
