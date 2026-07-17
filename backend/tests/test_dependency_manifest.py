from pathlib import Path
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
