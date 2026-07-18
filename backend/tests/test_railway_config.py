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
    assert "startCommand" not in config["deploy"]
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


def test_frontend_build_and_start_are_explicit_from_frontend_root():
    config = _config("frontend")

    assert config["build"]["builder"] == "RAILPACK"
    assert config["build"]["buildCommand"] == "npm ci && npm run build"
    assert config["deploy"]["startCommand"] == "npm run start -- -p $PORT"


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


def test_railway_start_commands_never_launch_or_import_browser_collector():
    forbidden = ("collector", "selenium", "chrome", "chromium", "browser")

    for name in CONFIG_PATHS:
        command = str(_config(name)["deploy"].get("startCommand", "")).casefold()
        assert not any(term in command for term in forbidden), (name, command)


def test_deployment_docs_define_dashboard_contract_and_safety_limits():
    railway_docs = Path("docs/deployment/RAILWAY.md").read_text()
    readme = Path("README.md").read_text()
    combined = railway_docs + "\n" + readme

    assert "Root Directory" in railway_docs
    assert "| `backend` | `/` | `/backend/railway.api.toml`" in railway_docs
    assert "| `worker` | `/` | `/backend/railway.worker.toml`" in railway_docs
    assert (
        "| `frontend` | `/frontend` | `/frontend/railway.toml`"
        in railway_docs
    )
    for config_path in (
        "/backend/railway.api.toml",
        "/backend/railway.worker.toml",
        "/frontend/railway.toml",
    ):
        assert config_path in railway_docs
    assert "backend/Dockerfile" in combined
    assert "生产" in railway_docs and "Dockerfile" in railway_docs
    assert "严格单副本" in railway_docs
    assert "FARESNIPER_LANGSMITH_TRACING=true" in combined
    assert "LANGSMITH_TRACING=false" in combined
    assert "LANGCHAIN_TRACING_V2=false" in combined
    assert "不要开启 `LANGCHAIN_TRACING_V2`" in railway_docs
    assert "VARIFLIGHT_API_KEY=" in railway_docs
    assert "未配置" in railway_docs and "hourly_scrape" in railway_docs
    assert "root `railway.toml`" not in combined
    assert "根目录的 [`railway.toml`]" not in combined
    assert "nixpacks build . --config backend/nixpacks.toml" in railway_docs
    assert "alembic -c backend/alembic.ini current --check-heads" in railway_docs


def test_deployment_docs_keep_collector_secrets_out_of_worker_variables():
    railway_docs = Path("docs/deployment/RAILWAY.md").read_text()
    backend_block = railway_docs.split("## Backend Variables", 1)[1].split(
        "## Worker Variables", 1
    )[0]
    worker_block = railway_docs.split("## Worker Variables", 1)[1].split(
        "## Frontend Variables", 1
    )[0]
    worker_env = worker_block.split("```dotenv", 1)[1].split("```", 1)[0]

    assert "CTRIP_COLLECTOR_TOKEN=" in backend_block
    assert "FLYAI_API_KEY=" in backend_block
    assert "SERPAPI_API_KEY=" in backend_block
    assert "CTRIP_COLLECTOR_TOKEN" not in worker_env
    assert "FLYAI_API_KEY" not in worker_env
    assert "SERPAPI_API_KEY" not in worker_env
    assert "CHROME" not in worker_env.upper()
    assert "COOKIE" not in worker_env.upper()
    assert "VAPID_PRIVATE_KEY=" in worker_env
    assert "VAPID_SUBJECT=" in worker_env

    frontend_block = railway_docs.split("## Frontend Variables", 1)[1].split(
        "## LangSmith", 1
    )[0]
    assert "NEXT_PUBLIC_VAPID_PUBLIC_KEY=" in frontend_block

    frontend_env = Path("frontend/.env.example").read_text()
    assert "NEXT_PUBLIC_VAPID_PUBLIC_KEY=" in frontend_env


def test_mac_collector_runbook_covers_install_operations_and_recovery():
    runbook = Path("docs/deployment/MAC_CTRIP_COLLECTOR.md").read_text()

    for required in (
        "scripts/install_macos_collector.sh",
        "doctor",
        "login",
        "--no-proxy-server",
        "Clash Verge",
        "launchctl print",
        "collector.log",
        "CTRIP_COLLECTOR_TOKEN",
        "CAPTCHA",
        "睡眠",
        "scripts/uninstall_macos_collector.sh",
        "~/.faresniper/ctrip-profile",
        "保留在本机",
    ):
        assert required in runbook


def test_readme_describes_all_china_airports_and_mac_collection_boundary():
    readme = Path("README.md").read_text()

    assert "270" in readme
    assert "18" in readme
    assert "288" in readme
    assert "Mac" in readme
    assert "Railway 不运行 Chrome" in readme
    assert "docs/deployment/MAC_CTRIP_COLLECTOR.md" in readme


def test_live_verification_docs_use_near_future_date_and_safe_session_token():
    readme = Path("README.md").read_text()
    railway_docs = Path("docs/deployment/RAILWAY.md").read_text()
    combined = readme + "\n" + railway_docs

    assert "2099-" not in combined
    assert "timedelta(days=14)" in combined
    assert 'DEPART_DATE="$(' in combined
    assert '--depart-date "$DEPART_DATE"' in combined
    assert "/api/session" in railway_docs
    assert 'FARESNIPER_VERIFY_JWT="$(' in railway_docs
    assert "unset FARESNIPER_VERIFY_JWT" in railway_docs
