from pathlib import Path
import json


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
