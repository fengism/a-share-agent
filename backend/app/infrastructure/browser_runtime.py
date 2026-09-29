"""Shared browser launch policy for the backend runtime."""

import logging
import os
import platform
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FULL_CHROMIUM_CHANNEL = "chromium"


def _extra_library_dirs() -> list[str]:
    """Locate local lib directories containing supplementary system libraries (e.g. libatk)."""
    candidate_dirs = [Path(sys.prefix) / "lib" / "extra-libs", Path(sys.prefix) / "lib"]
    triplet = {
        "x86_64": "x86_64-linux-gnu",
        "amd64": "x86_64-linux-gnu",
        "aarch64": "aarch64-linux-gnu",
        "arm64": "aarch64-linux-gnu",
    }.get(platform.machine().lower())
    if sys.platform == "linux" and triplet:
        candidate_dirs.append(Path.home() / ".local" / "lib" / "extra-libs" / "usr" / "lib" / triplet)
    candidate_dirs.append(Path.home() / ".local" / "lib")
    extra_paths: list[str] = []
    for path in candidate_dirs:
        try:
            if path.is_dir():
                extra_paths.append(str(path))
        except OSError as exc:
            # 补充库目录是可选项；挂载卷权限或 I/O 异常不应阻断服务启动/浏览器环境构建。
            logger.warning("跳过无法探测的可选浏览器库目录 path=%s error=%s", path, exc)
    return extra_paths


def _merge_library_paths(existing_ld: str, extra_paths: list[str]) -> str | None:
    existing_parts = [p for p in existing_ld.split(":") if p]
    new_parts = [p for p in extra_paths if p not in existing_parts]
    if not new_parts:
        return None
    return ":".join(new_parts + existing_parts)


def ensure_browser_library_paths() -> None:
    """把补充库目录写入当前进程的 LD_LIBRARY_PATH。

    launch_full_chromium 会显式注入该路径，但 stealth 等第三方链路直接以当前进程
    环境派生浏览器子进程；在启动阶段统一合入一次，保证所有子进程都能解析
    libatk/libatk-bridge 等缺失的系统库。幂等，可重复调用。
    """
    extra_paths = _extra_library_dirs()
    if not extra_paths:
        return
    combined = _merge_library_paths(os.environ.get("LD_LIBRARY_PATH", ""), extra_paths)
    if combined is not None:
        os.environ["LD_LIBRARY_PATH"] = combined


def _build_browser_env(custom_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Construct process environment with extra library search paths if present."""
    env = dict(os.environ)
    if custom_env:
        env.update(custom_env)

    combined = _merge_library_paths(env.get("LD_LIBRARY_PATH", ""), _extra_library_dirs())
    if combined is not None:
        env["LD_LIBRARY_PATH"] = combined

    return env


def full_chromium_launch_options(
    *,
    args: Sequence[str],
    proxy: Mapping[str, str] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """构建完整版 Chromium 的启动参数，async/sync 两条启动路径共用。"""
    launch_args = list(args)
    if "--disable-dev-shm-usage" not in launch_args:
        launch_args.append("--disable-dev-shm-usage")

    options: dict[str, Any] = {
        "channel": FULL_CHROMIUM_CHANNEL,
        "headless": True,
        "args": launch_args,
        "env": _build_browser_env(env),
    }
    if proxy is not None:
        options["proxy"] = dict(proxy)
    return options


async def launch_full_chromium(
    browser_type: Any,
    *,
    args: Sequence[str],
    proxy: Mapping[str, str] | None = None,
    env: Mapping[str, str] | None = None,
) -> Any:
    """Launch the installed full Chromium binary in headless mode.

    Explicitly selecting the ``chromium`` channel prevents Playwright from
    falling back to its separate headless-shell artifact. The Docker image can
    therefore install Chromium with ``--no-shell``.
    """
    return await browser_type.launch(**full_chromium_launch_options(args=args, proxy=proxy, env=env))
