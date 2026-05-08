import importlib
import pathlib
import subprocess

import pytest

LEGACY_PATHS = ["backend/services/search_service.py", "backend/llm/client.py"]
LEGACY_MODULES = ["backend.services.search_service", "backend.llm.client"]


def test_legacy_files_absent():
    for p in LEGACY_PATHS:
        assert not pathlib.Path(p).exists(), f"legacy file {p} should be removed"


def test_legacy_modules_unimportable():
    for mod in LEGACY_MODULES:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(mod)


def test_no_residual_imports():
    """grep 整个 backend/ 不应该再有对旧模块的 import 残留。"""
    cmd = [
        "grep", "-rn", "-E",
        r"from backend\.services\.search_service|from backend\.llm\.client"
        r"|import backend\.services\.search_service|import backend\.llm\.client",
        "backend/",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    assert out.returncode != 0, f"residual imports:\n{out.stdout}"
