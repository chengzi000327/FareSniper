from __future__ import annotations

from pathlib import Path
import tomllib


CONFIG_PATHS = {
    "api": Path("backend/railway.api.toml"),
    "worker": Path("backend/railway.worker.toml"),
    "frontend": Path("frontend/railway.toml"),
}


def _config(name: str) -> dict:
    return tomllib.loads(CONFIG_PATHS[name].read_text())


def test_each_railway_file_describes_one_official_deployment():
    assert not Path("railway.toml").exists()

    for path in CONFIG_PATHS.values():
        config = tomllib.loads(path.read_text())
        assert set(config) == {"build", "deploy"}
        assert "services" not in config
        assert isinstance(config["build"], dict)
        assert isinstance(config["deploy"], dict)


def test_api_uses_shared_backend_dockerfile_and_predeploy_migration():
    config = _config("api")

    assert config["build"] == {
        "builder": "DOCKERFILE",
        "dockerfilePath": "backend/Dockerfile",
    }
    assert config["deploy"]["preDeployCommand"] == [
        "alembic -c backend/alembic.ini upgrade head"
    ]
    assert config["deploy"]["startCommand"] == (
        "uvicorn backend.main:app --host 0.0.0.0 --port $PORT"
    )
    assert config["deploy"]["healthcheckPath"] == "/health"


def test_worker_uses_shared_image_without_migration():
    config = _config("worker")

    assert config["build"] == {
        "builder": "DOCKERFILE",
        "dockerfilePath": "backend/Dockerfile",
    }
    assert "preDeployCommand" not in config["deploy"]
    assert config["deploy"]["startCommand"] == (
        "python -m backend.workers.run_all"
    )


def test_frontend_build_and_start_are_explicit_from_repo_root():
    config = _config("frontend")

    assert config["build"]["builder"] == "RAILPACK"
    assert config["build"]["buildCommand"] == (
        "npm --prefix frontend ci && npm --prefix frontend run build"
    )
    assert config["deploy"]["startCommand"] == (
        "npm --prefix frontend run start -- -p $PORT"
    )


def test_railway_configs_only_use_supported_keys():
    allowed_build = {"builder", "dockerfilePath", "buildCommand"}
    allowed_deploy = {
        "preDeployCommand",
        "startCommand",
        "healthcheckPath",
        "healthcheckTimeout",
        "restartPolicyType",
        "restartPolicyMaxRetries",
    }

    for name in CONFIG_PATHS:
        config = _config(name)
        assert set(config["build"]) <= allowed_build
        assert set(config["deploy"]) <= allowed_deploy


def test_deployment_docs_define_dashboard_contract_and_safety_limits():
    railway_docs = Path("docs/deployment/RAILWAY.md").read_text()
    readme = Path("README.md").read_text()
    combined = railway_docs + "\n" + readme

    assert "Root Directory" in railway_docs
    assert "`/`" in railway_docs
    for config_path in (
        "/backend/railway.api.toml",
        "/backend/railway.worker.toml",
        "/frontend/railway.toml",
    ):
        assert config_path in railway_docs
    assert "backend/Dockerfile" in combined
    assert "生产" in railway_docs and "Dockerfile" in railway_docs
    assert "严格单副本" in railway_docs
    assert "LANGCHAIN_TRACING_V2=false" in combined
    assert "不要开启 `LANGCHAIN_TRACING_V2`" in railway_docs
    assert "VARIFLIGHT_API_KEY=" in railway_docs
    assert "未配置" in railway_docs and "hourly_scrape" in railway_docs
    assert "root `railway.toml`" not in combined
    assert "根目录的 [`railway.toml`]" not in combined
