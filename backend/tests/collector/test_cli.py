from __future__ import annotations

import subprocess
import sys
from pathlib import Path


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
    assert "chmod 600 \"$ENV_FILE\"" in install
    assert "launchctl bootstrap" in install
    assert "launchctl kickstart" in install
    assert "rm -rf" not in uninstall
    assert "ctrip-profile" in uninstall


def test_collector_requirements_are_isolated_from_railway_runtime():
    root = Path(__file__).parents[3]
    runtime = (root / "backend/requirements.txt").read_text(encoding="utf-8")
    collector = (root / "backend/requirements-collector.txt").read_text(
        encoding="utf-8"
    )

    assert "selenium" not in runtime.casefold()
    assert "-r requirements.txt" in collector
    assert "selenium>=4.22,<5.0" in collector
