from __future__ import annotations

import os
import plistlib
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.application.contracts.collector import CollectorErrorCode
from backend.collector import cli


_COLLECTOR_RUNTIME_FILES = {
    "backend/__init__.py",
    "backend/config.py",
    "backend/collector/__init__.py",
    "backend/collector/browser.py",
    "backend/collector/cli.py",
    "backend/collector/client.py",
    "backend/collector/runner.py",
    "backend/application/__init__.py",
    "backend/application/contracts/__init__.py",
    "backend/application/contracts/collector.py",
    "backend/application/contracts/flight_provider.py",
    "backend/application/services/__init__.py",
    "backend/application/services/airport_catalog.py",
    "backend/application/services/domestic_fees.py",
    "backend/application/services/flight_dates.py",
    "backend/application/services/flight_query.py",
    "backend/infrastructure/__init__.py",
    "backend/infrastructure/flight_data/__init__.py",
    "backend/infrastructure/flight_data/ctrip_parser.py",
    "backend/schemas/__init__.py",
    "backend/schemas/collector.py",
    "backend/utils/__init__.py",
    "backend/utils/airport_codes.py",
    "backend/data/china_airports.json",
}


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _installer_sandbox(
    tmp_path,
    *,
    setting_line: str,
    configured: bool = False,
    home_name: str = "home",
    config_name: str = "config",
):
    root = Path(__file__).parents[3]
    sandbox = tmp_path / "repo"
    scripts = sandbox / "scripts"
    scripts.mkdir(parents=True)
    installer = scripts / "install_macos_collector.sh"
    shutil.copy2(root / "scripts/install_macos_collector.sh", installer)

    template = sandbox / "deploy/macos"
    template.mkdir(parents=True)
    shutil.copy2(
        root / "deploy/macos/com.faresniper.ctrip-collector.plist.template",
        template / "com.faresniper.ctrip-collector.plist.template",
    )
    for relative in _COLLECTOR_RUNTIME_FILES:
        source = sandbox / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, source)
    (sandbox / "backend/requirements-collector.txt").write_text(
        "# test requirements\n",
        encoding="utf-8",
    )

    forbidden_sources = {
        "backend/.env": "MODEL_API_KEY=must-not-copy\n",
        "backend/tests/test_secret.py": "SECRET = 'must-not-copy'\n",
        "backend/collector/__pycache__/cli.pyc": "must-not-copy\n",
        "backend/.pytest_cache/state": "must-not-copy\n",
        "backend/private-secret.pem": "must-not-copy\n",
        "backend/api/unneeded.py": "# must-not-copy\n",
    }
    for relative, content in forbidden_sources.items():
        source = sandbox / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(content, encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "uname",
        "#!/bin/sh\nprintf 'Darwin\\n'\n",
    )
    real_python = shlex.quote(sys.executable)
    _write_executable(
        fake_bin / "python3",
        "#!/bin/sh\n"
        "if [ \"$1\" = '-' ] && [ -n \"${2:-}\" ]; then\n"
        "  printf 'manage:%s\\n' \"$2\" >>\"$FARESNIPER_TEST_EVENT_LOG\"\n"
        "  if [ \"$2\" = 'swap' ] "
        "&& [ \"${FARESNIPER_TEST_FAIL_STEP:-}\" = 'swap' ]; then\n"
        "    cat >/dev/null\n"
        "    exit 74\n"
        "  fi\n"
        "  if [ \"$2\" = 'rollback' ] "
        "&& [ \"${FARESNIPER_TEST_FAIL_ROLLBACK:-}\" = '1' ]; then\n"
        "    cat >/dev/null\n"
        "    exit 77\n"
        "  fi\n"
        "fi\n"
        "if [ \"$1\" = '-m' ] && [ \"$2\" = 'venv' ]; then\n"
        "  printf 'venv:%s\\n' \"$3\" "
        ">>\"$FARESNIPER_TEST_EVENT_LOG\"\n"
        "  mkdir -p \"$3/bin\"\n"
        "  cat >\"$3/bin/python\" <<'PYTHON'\n"
        "#!/bin/sh\n"
        "if [ \"$1\" = '-m' ] && [ \"$2\" = 'pip' ]; then\n"
        "  printf 'pip:%s\\n' \"$*\" "
        ">>\"$FARESNIPER_TEST_EVENT_LOG\"\n"
        "  if [ \"${FARESNIPER_TEST_FAIL_STEP:-}\" = 'pip' ]; then\n"
        "    exit 71\n"
        "  fi\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$1\" = '-m' ] && "
        "[ \"$2\" = 'backend.collector.cli' ]; then\n"
        "  printf 'doctor:%s\\n' \"$*\" "
        ">>\"$FARESNIPER_TEST_EVENT_LOG\"\n"
        "  if [ \"${FARESNIPER_TEST_FAIL_STEP:-}\" = 'doctor' ]; then\n"
        "    exit 72\n"
        "  fi\n"
        f"  exec {real_python} -c "
        "'import backend.collector.cli; import backend.collector.runner'\n"
        "fi\n"
        f"exec {real_python} \"$@\"\n"
        "PYTHON\n"
        "  chmod +x \"$3/bin/python\"\n"
        "  exit 0\n"
        "fi\n"
        f"exec {real_python} \"$@\"\n",
    )
    _write_executable(
        fake_bin / "plutil",
        "#!/bin/sh\n"
        "printf 'plist:%s\\n' \"$*\" "
        ">>\"$FARESNIPER_TEST_EVENT_LOG\"\n"
        "if [ \"${FARESNIPER_TEST_FAIL_STEP:-}\" = 'plist' ]; then\n"
        "  exit 73\n"
        "fi\n"
        "exit 0\n",
    )
    _write_executable(
        fake_bin / "sleep",
        "#!/bin/sh\n"
        "printf 'sleep:%s\\n' \"$*\" >>\"$FARESNIPER_TEST_EVENT_LOG\"\n",
    )
    _write_executable(
        fake_bin / "launchctl",
        "#!/bin/sh\n"
        "set -eu\n"
        "command=$1\n"
        "printf 'launchctl:%s\\n' \"$*\" "
        ">>\"$FARESNIPER_TEST_EVENT_LOG\"\n"
        "case \"$command\" in\n"
        "  print)\n"
        "    state=$(cat \"$FARESNIPER_TEST_LAUNCH_STATE\")\n"
        "    if [ \"$state\" = unloading ]; then\n"
        "      remaining=$(cat \"$FARESNIPER_TEST_UNLOAD_REMAINING\")\n"
        "      if [ \"$remaining\" -gt 0 ]; then\n"
        "        printf '%s\\n' \"$((remaining - 1))\" "
        ">\"$FARESNIPER_TEST_UNLOAD_REMAINING\"\n"
        "        exit 0\n"
        "      fi\n"
        "      printf 'unloaded\\n' >\"$FARESNIPER_TEST_LAUNCH_STATE\"\n"
        "      exit 1\n"
        "    fi\n"
        "    [ \"$state\" = loaded ]\n"
        "    ;;\n"
        "  bootout)\n"
        "    if [ \"${FARESNIPER_TEST_FAIL_STEP:-}\" = bootout ]; then\n"
        "      exit 75\n"
        "    fi\n"
        "    bootouts=$(cat \"$FARESNIPER_TEST_BOOTOUT_ATTEMPTS\")\n"
        "    bootouts=$((bootouts + 1))\n"
        "    printf '%s\\n' \"$bootouts\" "
        ">\"$FARESNIPER_TEST_BOOTOUT_ATTEMPTS\"\n"
        "    lag=${FARESNIPER_TEST_UNLOAD_LAG_PRINTS:-0}\n"
        "    if [ \"$bootouts\" -gt 1 ] "
        "&& [ -n \"${FARESNIPER_TEST_ROLLBACK_UNLOAD_LAG_PRINTS:-}\" ]; then\n"
        "      lag=$FARESNIPER_TEST_ROLLBACK_UNLOAD_LAG_PRINTS\n"
        "    fi\n"
        "    if [ \"$lag\" -gt 0 ]; then\n"
        "      printf 'unloading\\n' >\"$FARESNIPER_TEST_LAUNCH_STATE\"\n"
        "      printf '%s\\n' \"$lag\" "
        ">\"$FARESNIPER_TEST_UNLOAD_REMAINING\"\n"
        "    else\n"
        "      printf 'unloaded\\n' >\"$FARESNIPER_TEST_LAUNCH_STATE\"\n"
        "    fi\n"
        "    ;;\n"
        "  bootstrap)\n"
        "    attempts=$(cat \"$FARESNIPER_TEST_BOOTSTRAP_ATTEMPTS\")\n"
        "    attempts=$((attempts + 1))\n"
        "    printf '%s\\n' \"$attempts\" "
        ">\"$FARESNIPER_TEST_BOOTSTRAP_ATTEMPTS\"\n"
        "    mode=${FARESNIPER_TEST_BOOTSTRAP_MODE:-success}\n"
        "    if [ \"${FARESNIPER_TEST_FAIL_STEP:-}\" = bootstrap ] "
        "&& [ \"$attempts\" -le 4 ]; then\n"
        "      exit 76\n"
        "    fi\n"
        "    if [ \"$mode\" = transient ] && [ \"$attempts\" -eq 1 ]; then\n"
        "      exit 76\n"
        "    fi\n"
        "    if [ \"$mode\" = rollback-transient ] "
        "&& [ \"$attempts\" -eq 2 ]; then\n"
        "      exit 76\n"
        "    fi\n"
        "    if [ \"$mode\" = loaded-error ] && [ \"$attempts\" -eq 1 ]; then\n"
        "      printf 'loaded\\n' >\"$FARESNIPER_TEST_LAUNCH_STATE\"\n"
        "      exit 76\n"
        "    fi\n"
        "    if [ \"$mode\" = persistent-new ] "
        "&& ! grep -q old-plist \"$3\"; then\n"
        "      exit 76\n"
        "    fi\n"
        "    printf 'loaded\\n' >\"$FARESNIPER_TEST_LAUNCH_STATE\"\n"
        "    ;;\n"
        "  kickstart)\n"
        "    if [ \"${FARESNIPER_TEST_FAIL_STEP:-}\" = kickstart ] "
        "&& [ ! -f \"$FARESNIPER_TEST_FAIL_USED\" ]; then\n"
        "      : >\"$FARESNIPER_TEST_FAIL_USED\"\n"
        "      exit 76\n"
        "    fi\n"
        "    ;;\n"
        "esac\n",
    )

    home = tmp_path / home_name
    config_home = tmp_path / config_name
    env_file = config_home / "faresniper" / "collector.env"
    env_file.parent.mkdir(parents=True)
    credentials = (
        "FARESNIPER_API_URL=https://collector.example.test\n"
        "CTRIP_COLLECTOR_TOKEN=test-token\n"
        if configured
        else "FARESNIPER_API_URL=\nCTRIP_COLLECTOR_TOKEN=\n"
    )
    env_file.write_text(f"{credentials}{setting_line}\n", encoding="utf-8")
    event_log = tmp_path / "events.log"
    launch_state = tmp_path / "launch-state"
    fail_used = tmp_path / "fail-used"
    unload_remaining = tmp_path / "unload-remaining"
    bootstrap_attempts = tmp_path / "bootstrap-attempts"
    bootout_attempts = tmp_path / "bootout-attempts"
    event_log.write_text("", encoding="utf-8")
    launch_state.write_text("unloaded\n", encoding="utf-8")
    unload_remaining.write_text("0\n", encoding="utf-8")
    bootstrap_attempts.write_text("0\n", encoding="utf-8")
    bootout_attempts.write_text("0\n", encoding="utf-8")
    process_env = {
        **{
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX"}
        },
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(config_home),
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FARESNIPER_TEST_EVENT_LOG": str(event_log),
        "FARESNIPER_TEST_LAUNCH_STATE": str(launch_state),
        "FARESNIPER_TEST_FAIL_USED": str(fail_used),
        "FARESNIPER_TEST_UNLOAD_REMAINING": str(unload_remaining),
        "FARESNIPER_TEST_BOOTSTRAP_ATTEMPTS": str(bootstrap_attempts),
        "FARESNIPER_TEST_BOOTOUT_ATTEMPTS": str(bootout_attempts),
    }
    return SimpleNamespace(
        repo=sandbox,
        installer=installer,
        home=home,
        env_file=env_file,
        process_env=process_env,
        forbidden_sources=forbidden_sources,
        event_log=event_log,
        launch_state=launch_state,
        fail_used=fail_used,
        unload_remaining=unload_remaining,
        bootstrap_attempts=bootstrap_attempts,
        bootout_attempts=bootout_attempts,
    )


def _run_installer(
    sandbox,
    *,
    activate: bool = False,
    fail_step: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = dict(sandbox.process_env)
    if fail_step is not None:
        environment["FARESNIPER_TEST_FAIL_STEP"] = fail_step
    if extra_env is not None:
        environment.update(extra_env)
    return subprocess.run(
        [
            "bash",
            str(sandbox.installer),
            *(["--activate"] if activate else []),
        ],
        cwd=sandbox.repo,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )


def _runtime_cache_paths(runtime_dir: Path) -> list[Path]:
    return [
        path
        for path in runtime_dir.rglob("*")
        if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
    ]


def _seed_loaded_install(sandbox) -> dict[str, bytes]:
    state_dir = sandbox.home / ".faresniper"
    resources = {
        "runtime": state_dir / "runtime/old-runtime.txt",
        "venv": state_dir / "venv/old-venv.txt",
        "profile": state_dir / "ctrip-profile/.login-confirmed",
        "logs": state_dir / "logs/collector.log",
        "plist": (
            sandbox.home
            / "Library/LaunchAgents/com.faresniper.ctrip-collector.plist"
        ),
        "env": sandbox.env_file,
    }
    payloads = {
        "runtime": b"old-runtime\n",
        "venv": b"old-venv\n",
        "profile": b"logged-in\n",
        "logs": b"old-log\n",
        "plist": b"old-plist\n",
        "env": sandbox.env_file.read_bytes(),
    }
    for name, path in resources.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payloads[name])
    sandbox.launch_state.write_text("loaded\n", encoding="utf-8")
    return payloads


def _assert_old_resources_preserved(sandbox, payloads: dict[str, bytes]) -> None:
    state_dir = sandbox.home / ".faresniper"
    paths = {
        "runtime": state_dir / "runtime/old-runtime.txt",
        "venv": state_dir / "venv/old-venv.txt",
        "profile": state_dir / "ctrip-profile/.login-confirmed",
        "logs": state_dir / "logs/collector.log",
        "plist": (
            sandbox.home
            / "Library/LaunchAgents/com.faresniper.ctrip-collector.plist"
        ),
        "env": sandbox.env_file,
    }
    for name, path in paths.items():
        assert path.read_bytes() == payloads[name]
    assert {
        str(path.relative_to(state_dir / "runtime"))
        for path in (state_dir / "runtime").rglob("*")
        if path.is_file()
    } == {"old-runtime.txt"}
    assert {
        str(path.relative_to(state_dir / "venv"))
        for path in (state_dir / "venv").rglob("*")
        if path.is_file()
    } == {"old-venv.txt"}


def _assert_old_install_preserved(sandbox, payloads: dict[str, bytes]) -> None:
    _assert_old_resources_preserved(sandbox, payloads)
    assert sandbox.launch_state.read_text(encoding="utf-8").strip() == "loaded"


def _managed_install_residue(sandbox) -> list[Path]:
    state_dir = sandbox.home / ".faresniper"
    return [
        path
        for path in state_dir.glob(".*")
        if any(
            marker in path.name
            for marker in ("stage", "rollback", "previous", "backup")
        )
    ]


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
    sandbox = _installer_sandbox(tmp_path, setting_line=setting_line)

    for _ in range(2):
        result = _run_installer(sandbox)
        assert result.returncode == 0, result.stderr

    assignments = [
        line
        for line in sandbox.env_file.read_text(encoding="utf-8").splitlines()
        if re.match(
            r"^\s*(?:export\s+)?FARESNIPER_CTRIP_HEADLESS=",
            line,
        )
    ]
    assert assignments == [setting_line]


def test_macos_installer_creates_tcc_safe_private_runtime(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
    )

    first = _run_installer(sandbox)
    assert first.returncode == 0, first.stderr

    state_dir = sandbox.home / ".faresniper"
    runtime_dir = state_dir / "runtime"
    venv_python = state_dir / "venv/bin/python"
    assert runtime_dir.is_dir(), "installer must create a private runtime"
    assert venv_python.is_file(), "installer must create a private venv"
    profile_marker = state_dir / "ctrip-profile/session-marker"
    profile_marker.write_text("preserve", encoding="utf-8")
    stale_runtime_file = runtime_dir / "backend/stale-secret.py"
    stale_runtime_file.write_text("remove", encoding="utf-8")

    second = _run_installer(sandbox)
    assert second.returncode == 0, second.stderr

    assert not _runtime_cache_paths(runtime_dir)
    copied_files = {
        str(path.relative_to(runtime_dir))
        for path in runtime_dir.rglob("*")
        if path.is_file()
    }
    assert copied_files == _COLLECTOR_RUNTIME_FILES
    assert venv_python.is_file()
    assert profile_marker.read_text(encoding="utf-8") == "preserve"
    assert not stale_runtime_file.exists()
    assert not list(state_dir.glob(".runtime-*"))
    for forbidden in sandbox.forbidden_sources:
        assert not (runtime_dir / forbidden).exists()

    import_check = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; "
                "import backend.collector.cli as cli; "
                "import backend.collector.runner; "
                "assert Path(cli.__file__).resolve().is_relative_to(Path.cwd())"
            ),
        ],
        cwd=runtime_dir,
        env={
            **os.environ,
            "PYTHONPATH": str(runtime_dir),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
    )
    assert import_check.returncode == 0, import_check.stderr

    plist_path = (
        sandbox.home
        / "Library/LaunchAgents/com.faresniper.ctrip-collector.plist"
    )
    plist_text = plist_path.read_text(encoding="utf-8")
    plist = plistlib.loads(plist_path.read_bytes())
    assert str(sandbox.repo) not in plist_text
    assert plist["WorkingDirectory"] == str(runtime_dir)
    assert plist["ProgramArguments"] == [
        str(venv_python),
        "-m",
        "backend.collector.cli",
        "--env-file",
        str(sandbox.env_file),
        "daemon",
    ]
    assert plist["EnvironmentVariables"]["PYTHONUNBUFFERED"] == "1"


def test_macos_installer_displayed_login_command_disables_bytecode(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        home_name="home with ' quote",
        config_name="config with ' quote",
    )
    installed = _run_installer(sandbox)
    assert installed.returncode == 0, installed.stderr

    runtime_dir = sandbox.home / ".faresniper/runtime"
    for cache_dir in runtime_dir.rglob("__pycache__"):
        shutil.rmtree(cache_dir)
    login_command = next(
        line.strip()
        for line in installed.stdout.splitlines()
        if "backend.collector.cli" in line and line.strip().endswith("login)")
    )

    login = subprocess.run(
        ["bash", "-c", login_command],
        cwd=sandbox.repo,
        env=sandbox.process_env,
        capture_output=True,
        text=True,
    )

    assert login.returncode == 0, login.stderr
    assert not _runtime_cache_paths(runtime_dir)
    assert "PYTHONDONTWRITEBYTECODE=1" in login_command


def test_macos_installer_prints_absolute_activation_path_when_invoked_relatively(
    tmp_path,
):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
    )

    result = subprocess.run(
        ["bash", "scripts/install_macos_collector.sh"],
        cwd=sandbox.repo,
        env=sandbox.process_env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    expected = f"{shlex.quote(str(sandbox.installer))} --activate"
    assert expected in result.stdout


def test_new_macos_env_uses_empty_profile_for_dotenv_safe_default(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        home_name="home with 'single' and \"double\" quotes",
        config_name="config with spaces",
    )
    sandbox.env_file.unlink()

    result = _run_installer(sandbox)

    assert result.returncode == 0, result.stderr
    env_text = sandbox.env_file.read_text(encoding="utf-8")
    assert "FARESNIPER_CTRIP_PROFILE=\n" in env_text
    environment = {
        **sandbox.process_env,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(sandbox.home / ".faresniper/runtime"),
    }
    environment.pop("FARESNIPER_CTRIP_PROFILE", None)
    loaded = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os, sys; from dotenv import load_dotenv; "
                "load_dotenv(sys.argv[1], override=True); "
                "from backend.collector.cli import _profile_dir; "
                "print(os.environ.get('FARESNIPER_CTRIP_PROFILE', '<missing>')); "
                "print(_profile_dir())"
            ),
            str(sandbox.env_file),
        ],
        cwd=sandbox.home / ".faresniper/runtime",
        env=environment,
        capture_output=True,
        text=True,
    )

    assert loaded.returncode == 0, loaded.stderr
    assert loaded.stdout.splitlines() == [
        "",
        str(sandbox.home / ".faresniper/ctrip-profile"),
    ]


def test_macos_installer_leaves_existing_profile_configuration_untouched(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
    )
    sandbox.env_file.write_text(
        sandbox.env_file.read_text(encoding="utf-8")
        + 'FARESNIPER_CTRIP_PROFILE="/custom/profile path"\n',
        encoding="utf-8",
    )
    original = sandbox.env_file.read_bytes()

    result = _run_installer(sandbox)

    assert result.returncode == 0, result.stderr
    assert sandbox.env_file.read_bytes() == original


def test_macos_installer_refuses_non_activate_upgrade_of_loaded_agent(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    payloads = _seed_loaded_install(sandbox)

    result = _run_installer(sandbox)

    assert result.returncode != 0
    assert "--activate" in result.stderr
    _assert_old_install_preserved(sandbox, payloads)
    assert not _managed_install_residue(sandbox)
    events = sandbox.event_log.read_text(encoding="utf-8")
    assert "pip:" not in events
    assert "launchctl:bootout" not in events


@pytest.mark.parametrize("fail_step", ["pip", "doctor", "plist"])
def test_macos_upgrade_validation_failure_preserves_loaded_install(
    tmp_path,
    fail_step,
):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    payloads = _seed_loaded_install(sandbox)

    result = _run_installer(sandbox, activate=True, fail_step=fail_step)

    assert result.returncode != 0
    _assert_old_install_preserved(sandbox, payloads)
    assert not _managed_install_residue(sandbox)
    events = sandbox.event_log.read_text(encoding="utf-8")
    assert "launchctl:bootout" not in events


def test_macos_upgrade_swap_failure_restores_loaded_service(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    payloads = _seed_loaded_install(sandbox)

    result = _run_installer(sandbox, activate=True, fail_step="swap")

    assert result.returncode != 0
    _assert_old_install_preserved(sandbox, payloads)
    assert not _managed_install_residue(sandbox)
    events = sandbox.event_log.read_text(encoding="utf-8")
    assert "manage:swap" in events
    assert "launchctl:bootout" in events
    assert "launchctl:bootstrap" in events
    assert "launchctl:kickstart" in events


def test_macos_upgrade_waits_until_bootout_is_observably_unloaded(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    _seed_loaded_install(sandbox)

    result = _run_installer(
        sandbox,
        activate=True,
        extra_env={"FARESNIPER_TEST_UNLOAD_LAG_PRINTS": "2"},
    )

    assert result.returncode == 0, result.stderr
    events = sandbox.event_log.read_text(encoding="utf-8").splitlines()
    bootout_index = next(
        index for index, event in enumerate(events) if event.startswith("launchctl:bootout")
    )
    swap_index = events.index("manage:swap")
    between = events[bootout_index + 1 : swap_index]
    assert sum(event.startswith("launchctl:print") for event in between) >= 3
    assert sum(event.startswith("sleep:") for event in between) >= 2


def test_macos_upgrade_aborts_boundedly_when_service_never_unloads(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    payloads = _seed_loaded_install(sandbox)

    result = _run_installer(
        sandbox,
        activate=True,
        extra_env={"FARESNIPER_TEST_UNLOAD_LAG_PRINTS": "100"},
    )

    assert result.returncode != 0
    _assert_old_install_preserved(sandbox, payloads)
    assert not _managed_install_residue(sandbox)
    events = sandbox.event_log.read_text(encoding="utf-8")
    assert "manage:swap" not in events
    assert 1 <= events.count("sleep:") <= 30
    assert "did not unload" in result.stderr.lower()


def test_macos_upgrade_bootstrap_retries_transient_eio(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    _seed_loaded_install(sandbox)

    result = _run_installer(
        sandbox,
        activate=True,
        extra_env={"FARESNIPER_TEST_BOOTSTRAP_MODE": "transient"},
    )

    assert result.returncode == 0, result.stderr
    events = sandbox.event_log.read_text(encoding="utf-8")
    assert events.count("launchctl:bootstrap") == 2
    assert "manage:rollback" not in events
    assert sandbox.launch_state.read_text(encoding="utf-8").strip() == "loaded"


def test_macos_upgrade_accepts_bootstrap_error_when_service_is_loaded(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    _seed_loaded_install(sandbox)

    result = _run_installer(
        sandbox,
        activate=True,
        extra_env={"FARESNIPER_TEST_BOOTSTRAP_MODE": "loaded-error"},
    )

    assert result.returncode == 0, result.stderr
    events = sandbox.event_log.read_text(encoding="utf-8")
    assert events.count("launchctl:bootstrap") == 1
    assert "launchctl:kickstart" in events
    assert "manage:rollback" not in events


def test_macos_upgrade_does_not_mask_persistently_invalid_new_plist(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    payloads = _seed_loaded_install(sandbox)

    result = _run_installer(
        sandbox,
        activate=True,
        extra_env={"FARESNIPER_TEST_BOOTSTRAP_MODE": "persistent-new"},
    )

    assert result.returncode != 0
    _assert_old_install_preserved(sandbox, payloads)
    assert not _managed_install_residue(sandbox)
    attempts = int(sandbox.bootstrap_attempts.read_text(encoding="utf-8"))
    assert 3 <= attempts <= 6
    assert "restoring the previous install" in result.stderr.lower()


@pytest.mark.parametrize("fail_step", ["bootstrap", "kickstart"])
def test_macos_upgrade_start_failure_rolls_back_and_restarts_old_service(
    tmp_path,
    fail_step,
):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    payloads = _seed_loaded_install(sandbox)

    result = _run_installer(sandbox, activate=True, fail_step=fail_step)

    assert result.returncode != 0
    _assert_old_install_preserved(sandbox, payloads)
    assert not _managed_install_residue(sandbox)
    events = sandbox.event_log.read_text(encoding="utf-8")
    assert "manage:swap" in events
    assert events.count("launchctl:bootstrap") >= 2
    assert events.count("launchctl:kickstart") >= 1


def test_macos_rollback_restart_retries_transient_bootstrap_failure(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    payloads = _seed_loaded_install(sandbox)

    result = _run_installer(
        sandbox,
        activate=True,
        fail_step="kickstart",
        extra_env={
            "FARESNIPER_TEST_BOOTSTRAP_MODE": "rollback-transient",
            "FARESNIPER_TEST_UNLOAD_LAG_PRINTS": "2",
        },
    )

    assert result.returncode != 0
    _assert_old_install_preserved(sandbox, payloads)
    assert not _managed_install_residue(sandbox)
    events = sandbox.event_log.read_text(encoding="utf-8").splitlines()
    assert sum(event.startswith("launchctl:bootstrap") for event in events) == 3
    assert sum(event.startswith("launchctl:kickstart") for event in events) == 2
    bootout_indexes = [
        index
        for index, event in enumerate(events)
        if event.startswith("launchctl:bootout")
    ]
    assert len(bootout_indexes) == 2
    rollback_index = events.index("manage:rollback")
    rollback_wait = events[bootout_indexes[1] + 1 : rollback_index]
    assert sum(event.startswith("launchctl:print") for event in rollback_wait) >= 3
    assert sum(event.startswith("sleep:") for event in rollback_wait) >= 2


def test_macos_cleanup_preserves_both_versions_when_failed_new_service_stays_loaded(
    tmp_path,
):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    payloads = _seed_loaded_install(sandbox)

    result = _run_installer(
        sandbox,
        activate=True,
        fail_step="kickstart",
        extra_env={"FARESNIPER_TEST_ROLLBACK_UNLOAD_LAG_PRINTS": "100"},
    )

    assert result.returncode != 0
    state_dir = sandbox.home / ".faresniper"
    assert not (state_dir / "runtime/old-runtime.txt").exists()
    assert not (state_dir / "venv/old-venv.txt").exists()
    assert (state_dir / "runtime/backend/collector/cli.py").is_file()
    assert (state_dir / "venv/bin/python").is_file()
    runtime_backup = next(state_dir.glob(".runtime-rollback.*"))
    venv_backup = next(state_dir.glob(".venv-rollback.*"))
    plist_backup = next(state_dir.glob(".plist-rollback.*"))
    assert (runtime_backup / "old-runtime.txt").read_bytes() == payloads["runtime"]
    assert (venv_backup / "old-venv.txt").read_bytes() == payloads["venv"]
    assert plist_backup.read_bytes() == payloads["plist"]
    assert not list(state_dir.glob(".*-stage.*"))
    events = sandbox.event_log.read_text(encoding="utf-8")
    assert "manage:rollback" not in events
    assert "manage:cleanup" not in events
    assert "manual recovery" in result.stderr.lower()


def test_macos_upgrade_preserves_backups_when_rollback_itself_fails(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    payloads = _seed_loaded_install(sandbox)
    environment = {
        **sandbox.process_env,
        "FARESNIPER_TEST_FAIL_STEP": "bootstrap",
        "FARESNIPER_TEST_FAIL_ROLLBACK": "1",
    }

    result = subprocess.run(
        ["bash", str(sandbox.installer), "--activate"],
        cwd=sandbox.repo,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "rollback failed" in result.stderr.lower()
    state_dir = sandbox.home / ".faresniper"
    runtime_backup = next(state_dir.glob(".runtime-rollback.*"))
    venv_backup = next(state_dir.glob(".venv-rollback.*"))
    plist_backup = next(state_dir.glob(".plist-rollback.*"))
    assert (runtime_backup / "old-runtime.txt").read_bytes() == payloads["runtime"]
    assert (venv_backup / "old-venv.txt").read_bytes() == payloads["venv"]
    assert plist_backup.read_bytes() == payloads["plist"]
    assert not list(state_dir.glob(".*-stage.*"))
    assert sandbox.launch_state.read_text(encoding="utf-8").strip() == "unloaded"


def test_macos_upgrade_validates_stages_before_atomic_activation(tmp_path):
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    payloads = _seed_loaded_install(sandbox)

    result = _run_installer(sandbox, activate=True)

    assert result.returncode == 0, result.stderr
    state_dir = sandbox.home / ".faresniper"
    assert not (state_dir / "runtime/old-runtime.txt").exists()
    assert not (state_dir / "venv/old-venv.txt").exists()
    assert (state_dir / "runtime/backend/collector/cli.py").is_file()
    assert (state_dir / "venv/bin/python").is_file()
    assert (state_dir / "ctrip-profile/.login-confirmed").read_bytes() == payloads[
        "profile"
    ]
    assert (state_dir / "logs/collector.log").read_bytes() == payloads["logs"]
    assert sandbox.env_file.read_bytes() == payloads["env"]
    assert sandbox.launch_state.read_text(encoding="utf-8").strip() == "loaded"
    assert not _managed_install_residue(sandbox)

    events = sandbox.event_log.read_text(encoding="utf-8").splitlines()
    venv_event = next(event for event in events if event.startswith("venv:"))
    assert "/.venv-stage." in venv_event
    doctor_indexes = [
        index for index, event in enumerate(events) if event.startswith("doctor:")
    ]
    plist_index = next(
        index for index, event in enumerate(events) if event.startswith("plist:")
    )
    bootout_index = next(
        index
        for index, event in enumerate(events)
        if event.startswith("launchctl:bootout")
    )
    assert len(doctor_indexes) == 2
    assert max(*doctor_indexes, plist_index) < bootout_index


def test_macos_uninstaller_removes_only_managed_runtime(tmp_path):
    root = Path(__file__).parents[3]
    home = tmp_path / "home"
    state_dir = home / ".faresniper"
    config_file = tmp_path / "config/faresniper/collector.env"
    preserved = [
        state_dir / "ctrip-profile/session-marker",
        state_dir / "logs/collector.log",
        state_dir / "runtime-keep/marker",
        config_file,
    ]
    removed = [state_dir / "runtime/module.py", state_dir / "venv/bin/python"]
    for path in [*preserved, *removed]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("sentinel", encoding="utf-8")

    plist_path = (
        home / "Library/LaunchAgents/com.faresniper.ctrip-collector.plist"
    )
    plist_path.parent.mkdir(parents=True)
    plist_path.write_text("plist", encoding="utf-8")
    fake_bin = tmp_path / "uninstall-bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "launchctl",
        "#!/bin/sh\n"
        "if [ \"$1\" = print ]; then exit 1; fi\n"
        "exit 0\n",
    )
    uninstaller = tmp_path / "uninstall_macos_collector.sh"
    shutil.copy2(root / "scripts/uninstall_macos_collector.sh", uninstaller)

    result = subprocess.run(
        ["bash", str(uninstaller)],
        env={
            **os.environ,
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert not plist_path.exists()
    assert not (state_dir / "runtime").exists()
    assert not (state_dir / "venv").exists()
    assert all(path.exists() for path in preserved)


def test_macos_uninstaller_aborts_without_deleting_when_bootout_fails(tmp_path):
    root = Path(__file__).parents[3]
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    payloads = _seed_loaded_install(sandbox)
    uninstaller = sandbox.repo / "scripts/uninstall_macos_collector.sh"
    shutil.copy2(root / "scripts/uninstall_macos_collector.sh", uninstaller)
    environment = {
        **sandbox.process_env,
        "FARESNIPER_TEST_FAIL_STEP": "bootout",
    }

    result = subprocess.run(
        ["bash", str(uninstaller)],
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    _assert_old_install_preserved(sandbox, payloads)
    assert "launchctl:bootout" in sandbox.event_log.read_text(encoding="utf-8")


def test_macos_uninstaller_waits_for_delayed_unload_before_deleting(tmp_path):
    root = Path(__file__).parents[3]
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    payloads = _seed_loaded_install(sandbox)
    uninstaller = sandbox.repo / "scripts/uninstall_macos_collector.sh"
    shutil.copy2(root / "scripts/uninstall_macos_collector.sh", uninstaller)
    environment = {
        **sandbox.process_env,
        "FARESNIPER_TEST_UNLOAD_LAG_PRINTS": "2",
    }

    result = subprocess.run(
        ["bash", str(uninstaller)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    state_dir = sandbox.home / ".faresniper"
    plist_path = sandbox.home / "Library/LaunchAgents/com.faresniper.ctrip-collector.plist"
    assert not (state_dir / "runtime").exists()
    assert not (state_dir / "venv").exists()
    assert not plist_path.exists()
    assert (state_dir / "ctrip-profile/.login-confirmed").read_bytes() == payloads[
        "profile"
    ]
    assert (state_dir / "logs/collector.log").read_bytes() == payloads["logs"]
    assert sandbox.env_file.read_bytes() == payloads["env"]
    events = sandbox.event_log.read_text(encoding="utf-8")
    assert events.count("launchctl:print") >= 4
    assert events.count("sleep:") >= 2


def test_macos_uninstaller_timeout_deletes_nothing(tmp_path):
    root = Path(__file__).parents[3]
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
        configured=True,
    )
    payloads = _seed_loaded_install(sandbox)
    uninstaller = sandbox.repo / "scripts/uninstall_macos_collector.sh"
    shutil.copy2(root / "scripts/uninstall_macos_collector.sh", uninstaller)
    environment = {
        **sandbox.process_env,
        "FARESNIPER_TEST_UNLOAD_LAG_PRINTS": "100",
    }

    result = subprocess.run(
        ["bash", str(uninstaller)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode != 0
    _assert_old_resources_preserved(sandbox, payloads)
    assert "did not unload" in result.stderr.lower()
    assert 1 <= sandbox.event_log.read_text(encoding="utf-8").count("sleep:") <= 30


def test_macos_uninstaller_rejects_raw_state_symlink_without_deleting(tmp_path):
    root = Path(__file__).parents[3]
    sandbox = _installer_sandbox(
        tmp_path,
        setting_line="FARESNIPER_CTRIP_HEADLESS=false",
    )
    external_state = tmp_path / "external-state"
    external_runtime = external_state / "runtime/module.py"
    external_venv = external_state / "venv/bin/python"
    for path in (external_runtime, external_venv):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("preserve", encoding="utf-8")
    sandbox.home.mkdir(parents=True)
    state_link = sandbox.home / ".faresniper"
    state_link.symlink_to(external_state, target_is_directory=True)
    plist_path = sandbox.home / "Library/LaunchAgents/com.faresniper.ctrip-collector.plist"
    plist_path.parent.mkdir(parents=True)
    plist_path.write_text("preserve-plist", encoding="utf-8")
    uninstaller = sandbox.repo / "scripts/uninstall_macos_collector.sh"
    shutil.copy2(root / "scripts/uninstall_macos_collector.sh", uninstaller)

    result = subprocess.run(
        ["bash", str(uninstaller)],
        env=sandbox.process_env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode != 0
    assert state_link.is_symlink()
    assert external_runtime.read_text(encoding="utf-8") == "preserve"
    assert external_venv.read_text(encoding="utf-8") == "preserve"
    assert plist_path.read_text(encoding="utf-8") == "preserve-plist"
    assert "symlink" in result.stderr.lower()


def test_macos_collector_docs_use_xdg_config_path_for_current_node_commands():
    root = Path(__file__).parents[3]
    docs = (root / "docs/deployment/MAC_CTRIP_COLLECTOR.md").read_text(
        encoding="utf-8"
    )

    expected = (
        'COLLECTOR_ENV_FILE="${XDG_CONFIG_HOME:-$HOME/.config}'
        '/faresniper/collector.env"'
    )
    assert expected in docs
    assert docs.count('--env-file "$COLLECTOR_ENV_FILE"') >= 4
    assert '--env-file "$HOME/.config/faresniper/collector.env"' not in docs
    xdg_export = (
        'export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-'
        '$HOME/.faresniper/config}"'
    )
    assert docs.count(xdg_export) >= 3
    assert 'INSTALLER_PATH="$(pwd -P)/scripts/install_macos_collector.sh"' in docs
    assert 'bash scripts/install_macos_collector.sh --activate' not in docs


def test_collector_requirements_are_isolated_from_railway_runtime():
    root = Path(__file__).parents[3]
    runtime = (root / "backend/requirements.txt").read_text(encoding="utf-8")
    collector = (root / "backend/requirements-collector.txt").read_text(
        encoding="utf-8"
    )

    assert "selenium" not in runtime.casefold()
    assert "-r requirements.txt" in collector
    assert "selenium>=4.22,<5.0" in collector
    assert "truststore>=0.10,<1.0" in collector


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
