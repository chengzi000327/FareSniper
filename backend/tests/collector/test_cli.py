from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.application.contracts.collector import CollectorErrorCode
from backend.collector import cli


def test_cli_import_does_not_initialize_backend_settings_early():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import backend.collector.cli; "
                "print('backend.config' in sys.modules)"
            ),
        ],
        cwd=Path(__file__).parents[3],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"


def test_macos_installer_keeps_secrets_as_empty_placeholders():
    root = Path(__file__).parents[3]
    install = (root / "scripts/install_macos_collector.sh").read_text(
        encoding="utf-8"
    )
    uninstall = (root / "scripts/uninstall_macos_collector.sh").read_text(
        encoding="utf-8"
    )

    assert "FARESNIPER_API_URL=" in install
    assert "CTRIP_COLLECTOR_TOKEN=" in install
    assert "FARESNIPER_CTRIP_HEADLESS=false" in install
    assert "chmod 600 \"$ENV_FILE\"" in install
    assert "launchctl bootstrap" in install
    assert "launchctl kickstart" in install
    assert "rm -rf" not in uninstall
    assert "ctrip-profile" in uninstall


@pytest.mark.parametrize(
    "setting_line",
    [
        "export FARESNIPER_CTRIP_HEADLESS=true",
        "  FARESNIPER_CTRIP_HEADLESS=true",
        "  export FARESNIPER_CTRIP_HEADLESS=true",
    ],
)
def test_macos_installer_preserves_explicit_headless_setting_idempotently(
    tmp_path,
    setting_line,
):
    root = Path(__file__).parents[3]
    sandbox = tmp_path / "repo"
    scripts = sandbox / "scripts"
    scripts.mkdir(parents=True)
    installer = scripts / "install_macos_collector.sh"
    shutil.copy2(root / "scripts/install_macos_collector.sh", installer)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "uname").write_text(
        "#!/bin/sh\nprintf 'Darwin\\n'\n",
        encoding="utf-8",
    )
    (fake_bin / "python3").write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = '-m' ] && [ \"$2\" = 'venv' ]; then\n"
        "  mkdir -p \"$3/bin\"\n"
        "  printf '#!/bin/sh\\nexit 0\\n' >\"$3/bin/python\"\n"
        "  chmod +x \"$3/bin/python\"\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (fake_bin / "plutil").write_text(
        "#!/bin/sh\nexit 0\n",
        encoding="utf-8",
    )
    for command in ("uname", "python3", "plutil"):
        (fake_bin / command).chmod(0o755)

    home = tmp_path / "home"
    config_home = tmp_path / "config"
    env_file = config_home / "faresniper" / "collector.env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text(
        "FARESNIPER_API_URL=\n"
        "CTRIP_COLLECTOR_TOKEN=\n"
        f"{setting_line}\n",
        encoding="utf-8",
    )
    process_env = {
        **os.environ,
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(config_home),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
    }

    for _ in range(2):
        result = subprocess.run(
            ["bash", str(installer)],
            cwd=sandbox,
            env=process_env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    assignments = [
        line
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if re.match(
            r"^\s*(?:export\s+)?FARESNIPER_CTRIP_HEADLESS=",
            line,
        )
    ]
    assert assignments == [setting_line]


def test_collector_requirements_are_isolated_from_railway_runtime():
    root = Path(__file__).parents[3]
    runtime = (root / "backend/requirements.txt").read_text(encoding="utf-8")
    collector = (root / "backend/requirements-collector.txt").read_text(
        encoding="utf-8"
    )

    assert "selenium" not in runtime.casefold()
    assert "-r requirements.txt" in collector
    assert "selenium>=4.22,<5.0" in collector


@pytest.mark.asyncio
async def test_failed_login_removes_existing_confirmation_marker(
    tmp_path,
    monkeypatch,
):
    marker = tmp_path / cli.LOGIN_MARKER
    marker.touch()

    class LoggedOutBrowser:
        def __init__(self, **_kwargs):
            pass

        async def login(self):
            return CollectorErrorCode.login_required

        async def close(self):
            pass

    monkeypatch.setattr(cli, "_profile_dir", lambda: tmp_path)
    monkeypatch.setattr(cli, "CtripBrowser", LoggedOutBrowser)

    result = await cli._login()

    assert result == 1
    assert not marker.exists()


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        (None, True),
        ("true", True),
        (" TRUE ", True),
        ("false", False),
        (" FALSE ", False),
    ],
)
def test_ctrip_headless_configuration_preserves_default_and_parses_booleans(
    configured,
    expected,
    monkeypatch,
):
    if configured is None:
        monkeypatch.delenv("FARESNIPER_CTRIP_HEADLESS", raising=False)
    else:
        monkeypatch.setenv("FARESNIPER_CTRIP_HEADLESS", configured)

    assert cli._ctrip_headless() is expected


def test_ctrip_headless_configuration_rejects_ambiguous_values(monkeypatch):
    monkeypatch.setenv("FARESNIPER_CTRIP_HEADLESS", "sometimes")

    with pytest.raises(ValueError, match="FARESNIPER_CTRIP_HEADLESS"):
        cli._ctrip_headless()


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["once", "daemon"])
async def test_collection_commands_pass_configured_browser_mode(
    command,
    monkeypatch,
    tmp_path,
):
    browser_kwargs: list[dict[str, object]] = []

    class Browser:
        def __init__(self, **kwargs):
            browser_kwargs.append(kwargs)

        async def close(self):
            pass

    class Client:
        async def close(self):
            pass

    class Runner:
        def __init__(self, _client, _browser):
            pass

        async def run_once(self):
            return SimpleNamespace(status="idle", result_count=0)

        async def run_daemon(self, **_kwargs):
            pass

    from backend.collector import runner as runner_module

    monkeypatch.setenv("FARESNIPER_CTRIP_HEADLESS", "false")
    monkeypatch.setattr(cli, "_profile_dir", lambda: tmp_path)
    monkeypatch.setattr(cli, "_new_client", Client)
    monkeypatch.setattr(cli, "CtripBrowser", Browser)
    monkeypatch.setattr(runner_module, "CollectorRunner", Runner)

    if command == "once":
        assert await cli._run_once() == 0
    else:
        assert await cli._run_daemon(1.0) == 0

    assert browser_kwargs[0]["headless"] is False
