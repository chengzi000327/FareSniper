from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import platform
import shutil
import signal
import socket
from pathlib import Path

from dotenv import load_dotenv

from backend.collector.browser import CtripBrowser, DEFAULT_PROFILE_DIR
from backend.collector.client import CollectorApiClient


DEFAULT_ENV_FILE = Path.home() / ".config" / "faresniper" / "collector.env"
LOGIN_MARKER = ".login-confirmed"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FareSniper Ctrip collector")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--local-only", action="store_true")
    commands.add_parser("login")
    commands.add_parser("once")
    daemon = commands.add_parser("daemon")
    daemon.add_argument("--interval", type=float)
    return parser


def _profile_dir() -> Path:
    configured = os.getenv("FARESNIPER_CTRIP_PROFILE", "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_PROFILE_DIR


def _ctrip_headless() -> bool:
    configured = os.getenv("FARESNIPER_CTRIP_HEADLESS")
    if configured is None:
        return True
    normalized = configured.strip().casefold()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(
        "FARESNIPER_CTRIP_HEADLESS must be true or false"
    )


def _chrome_exists() -> bool:
    candidates = (
        shutil.which("Google Chrome"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    )
    return any(candidate and Path(candidate).exists() for candidate in candidates)


def _doctor(*, local_only: bool) -> int:
    problems: list[str] = []
    if platform.system() != "Darwin":
        problems.append("collector 仅支持 macOS")
    if importlib.util.find_spec("selenium") is None:
        problems.append("未安装 Selenium")
    if not _chrome_exists():
        problems.append("未找到 Google Chrome")

    profile = _profile_dir().resolve()
    default_root = (
        Path.home() / "Library/Application Support/Google/Chrome"
    ).resolve()
    if profile == default_root or profile.is_relative_to(default_root):
        problems.append("必须使用独立的携程 Chrome profile")
    else:
        profile.mkdir(parents=True, exist_ok=True, mode=0o700)

    if not local_only:
        if not os.getenv("FARESNIPER_API_URL", "").strip():
            problems.append("FARESNIPER_API_URL 未配置")
        if not os.getenv("CTRIP_COLLECTOR_TOKEN", "").strip():
            problems.append("CTRIP_COLLECTOR_TOKEN 未配置")
        if not (profile / LOGIN_MARKER).exists():
            problems.append("尚未完成 collector login")

    if problems:
        for problem in problems:
            print(f"[FAIL] {problem}")
        return 1
    print(f"[OK] collector profile: {profile}")
    return 0


def _node_id() -> str:
    configured = os.getenv("FARESNIPER_COLLECTOR_NODE_ID", "").strip()
    value = configured or f"mac-{socket.gethostname()}"
    return value[:128]


def _new_client() -> CollectorApiClient:
    return CollectorApiClient(
        base_url=os.getenv("FARESNIPER_API_URL", ""),
        token=os.getenv("CTRIP_COLLECTOR_TOKEN", ""),
        node_id=_node_id(),
    )


async def _login() -> int:
    profile = _profile_dir()
    marker = profile / LOGIN_MARKER
    marker.unlink(missing_ok=True)
    browser = CtripBrowser(profile_dir=profile)
    try:
        error = await browser.login()
    finally:
        await browser.close()
    if error is not None:
        print(f"登录未完成：{error.value}")
        return 1
    marker.touch(mode=0o600, exist_ok=True)
    print("携程专用 profile 已确认。")
    return 0


async def _run_once() -> int:
    from backend.collector.runner import CollectorRunner

    client = _new_client()
    browser = CtripBrowser(
        profile_dir=_profile_dir(),
        timeout_seconds=float(
            os.getenv("CTRIP_COLLECTION_TIMEOUT_SECONDS", "90")
        ),
        headless=_ctrip_headless(),
    )
    try:
        result = await CollectorRunner(client, browser).run_once()
        print(f"collector status={result.status} count={result.result_count}")
        return 0
    finally:
        await browser.close()
        await client.close()


async def _run_daemon(interval: float | None) -> int:
    from backend.collector.runner import CollectorRunner

    client = _new_client()
    browser = CtripBrowser(
        profile_dir=_profile_dir(),
        timeout_seconds=float(
            os.getenv("CTRIP_COLLECTION_TIMEOUT_SECONDS", "90")
        ),
        headless=_ctrip_headless(),
    )
    runner = CollectorRunner(client, browser)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for stop_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(stop_signal, stop.set)
        except NotImplementedError:
            pass

    async def wait_for_stop(seconds: float) -> bool:
        try:
            await asyncio.wait_for(stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            return False
        return True

    configured_interval = interval or float(
        os.getenv("FARESNIPER_COLLECTOR_INTERVAL_SECONDS", "60")
    )
    try:
        await runner.run_daemon(
            stop_requested=stop.is_set,
            interval_seconds=configured_interval,
            wait_for_stop=wait_for_stop,
        )
        return 0
    finally:
        await browser.close()
        await client.close()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_dotenv(args.env_file, override=False)
    if args.command == "doctor":
        return _doctor(local_only=args.local_only)
    if args.command == "login":
        return asyncio.run(_login())
    if args.command == "once":
        return asyncio.run(_run_once())
    return asyncio.run(_run_daemon(args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
