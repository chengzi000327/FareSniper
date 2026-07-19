from pathlib import Path, PurePosixPath
import json
import re


def test_backend_requirements_include_plan_dependencies():
    req = Path("backend/requirements.txt").read_text()
    for name in [
        "pydantic-settings",
        "PyJWT",
        "aiosqlite",
        "pywebpush",
        "playwright",
        "apscheduler",
    ]:
        assert name in req, f"missing dependency in backend/requirements.txt: {name}"


def _requirements(path: str) -> list[str]:
    return [
        line.strip()
        for line in Path(path).read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_selenium_is_isolated_to_the_mac_collector_manifest():
    runtime = _requirements("backend/requirements.txt")
    collector = _requirements("backend/requirements-collector.txt")

    assert not any(line.casefold().startswith("selenium") for line in runtime)
    assert collector.count("selenium>=4.22,<5.0") == 1
    assert collector[0] == "-r requirements.txt"


def test_collector_virtualenv_is_ignored():
    entries = {
        line.strip()
        for line in Path(".gitignore").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert ".venv-collector/" in entries


def test_backend_requires_validated_langsmith_conditional_tracing_runtime():
    requirements = [
        line.strip()
        for line in Path("backend/requirements.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    langsmith_requirements = [
        requirement
        for requirement in requirements
        if re.match(r"^langsmith(?:\[.*\])?(?:[<>=!~]|$)", requirement)
    ]

    assert len(langsmith_requirements) == 1
    lower_bound = re.search(
        r">=\s*(\d+)\.(\d+)\.(\d+)", langsmith_requirements[0]
    )
    assert lower_bound is not None
    assert tuple(map(int, lower_bound.groups())) >= (0, 8, 3)


def test_frontend_uses_npm_test_script():
    pkg = json.loads(Path("frontend/package.json").read_text())
    assert "test" in pkg["scripts"]
    assert "vitest" in pkg["scripts"]["test"]
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    for name in [
        "vitest",
        "jsdom",
        "@testing-library/react",
        "@testing-library/jest-dom",
    ]:
        assert name in deps, f"missing devDependency in frontend/package.json: {name}"


def test_nixpacks_pins_flyai_cli_and_node():
    text = Path("backend/nixpacks.toml").read_text()

    assert "nodejs_22" in text
    assert "python313" in text
    assert '"..."' in text
    assert "gcc" in text
    assert "backend/requirements.txt" in text
    assert "backend/third_party/flights_monitor/requirements.txt" not in text
    assert "npm install -g @fly-ai/flyai-cli@1.0.16" in text
    assert "npx" not in text
    assert "flyai config set" not in text
    assert "chromium" not in text.casefold()
    assert "chromedriver" not in text.casefold()

    import tomllib

    config = tomllib.loads(text)
    assert config["phases"]["install"]["dependsOn"] == ["setup"]
    assert config["start"]["cmd"] == (
        "sh -c 'exec /opt/venv/bin/uvicorn backend.main:app --host 0.0.0.0 "
        '--port "${PORT:-8000}"\''
    )
    assert config["variables"]["PYTHONUNBUFFERED"] == "1"


def test_nixpacks_provisions_python_venv_for_install_and_start():
    import tomllib

    config = tomllib.loads(Path("backend/nixpacks.toml").read_text())
    install = config["phases"]["install"]

    assert install["dependsOn"] == ["setup"]
    assert install["cmds"][0] == "python -m venv --copies /opt/venv"
    assert install["cmds"][1].startswith("/opt/venv/bin/pip install ")
    assert install["paths"] == ["/opt/venv/bin"]
    assert config["start"]["cmd"].startswith(
        "sh -c 'exec /opt/venv/bin/uvicorn backend.main:app "
    )


def test_backend_dockerfile_has_complete_shared_runtime():
    text = Path("backend/Dockerfile").read_text()

    assert "FROM node:22" in text
    assert "FROM python:3.13" in text
    assert "chromium" not in text.casefold()
    assert "chromedriver" not in text.casefold()
    assert "CHROME_BIN" not in text
    assert "CHROMEDRIVER_PATH" not in text
    assert "WORKDIR /app" in text
    assert "backend/requirements.txt" in text
    assert "backend/third_party/flights_monitor/requirements.txt" not in text
    assert "npm install -g @fly-ai/flyai-cli@1.0.16" in text
    assert "npx" not in text
    assert "flyai config set" not in text
    assert 'CMD ["uvicorn"' not in text
    cmd_line = next(line for line in text.splitlines() if line.startswith("CMD "))
    command = json.loads(cmd_line.removeprefix("CMD "))
    assert command[:2] == ["sh", "-c"]
    assert "exec uvicorn backend.main:app" in command[2]
    assert '"${PORT:-8000}"' in command[2]


def test_docker_context_excludes_secrets_and_build_artifacts():
    ordered_entries = [
        line.strip()
        for line in Path(".dockerignore").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    entries = set(ordered_entries)

    for required in {
        ".git",
        ".venv",
        "**/.venv",
        ".env",
        "**/.env",
        "node_modules",
        "**/node_modules",
        "**/__pycache__",
        ".pytest_cache",
        "**/.pytest_cache",
        ".coverage",
        "coverage",
        "**/coverage",
        ".superpowers",
        "tmp",
        "**/tmp",
        "frontend/.next",
    }:
        assert required in entries

    assert ".env*" in entries
    assert "**/.env*" in entries
    assert "!.env.example" in entries
    assert "!**/.env.example" in entries
    assert ordered_entries.index(".env*") < ordered_entries.index("!.env.example")
    assert ordered_entries.index("**/.env*") < ordered_entries.index(
        "!**/.env.example"
    )
    assert PurePosixPath(".env.local").match(".env*")
    assert PurePosixPath("backend/.env.production").match("**/.env*")
    assert PurePosixPath("backend/.env.example").match("!**/.env.example"[1:])

    assert "backend" not in entries
    assert "backend/requirements.txt" not in entries


def test_env_example_has_safe_flight_provider_defaults():
    lines = Path("backend/.env.example").read_text().splitlines()
    values = {
        key: value
        for line in lines
        if line and not line.lstrip().startswith("#") and "=" in line
        for key, value in [line.split("=", 1)]
    }

    assert values["ENABLE_MOCK_FALLBACK"] == "false"
    assert values["FLYAI_API_KEY"] == ""
    assert values["FLYAI_CLI_PATH"] == "flyai"
    assert values["SERPAPI_API_KEY"] == ""
    assert values["CTRIP_COLLECTOR_TOKEN"] == ""
    assert values["VARIFLIGHT_API_KEY"] == ""
    assert values["FLIGHT_PROVIDER_TIMEOUT_SECONDS"] == "10"
    assert values["CTRIP_SNAPSHOT_TTL_MINUTES"] == "75"
    assert values["CTRIP_REFRESH_BATCH_SIZE"] == "20"
    assert values["CTRIP_COLLECTION_TIMEOUT_SECONDS"] == "90"
    assert values["RUN_SCHEDULER_IN_API"] == "false"
    assert values["FARESNIPER_LANGSMITH_TRACING"] == "true"
    assert values["LANGSMITH_TRACING"] == "false"
    assert values["LANGCHAIN_TRACING_V2"] == "false"
    assert values["LANGSMITH_API_KEY"] == ""
    assert values["LANGSMITH_PROJECT"] == "faresniper"
