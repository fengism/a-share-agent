"""Cancellable PNG rendering in a disposable POSIX process group.

PNG jobs share the PDF permit; the worker, Node and Chromium descendants are
terminated before releasing that permit, including during process creation.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from app.configuration import get_settings
from app.core.exceptions import UpstreamUnavailableError
from app.infrastructure.cleanup import wait_for_cleanup
from app.infrastructure.render_queue import get_render_limiter as _limiter

_MAX_INPUT = 8 * 1024 * 1024
_MAX_OUTPUT = 32 * 1024 * 1024
_MAX_STDERR = 64 * 1024


_JOB_ENV = "TRADE_CHART_JOB"


def _job_groups(job_id: str) -> set[int]:
    """Find this job even after its Python/Node parent exited.

    Every process inherits a random per-job marker. Never log process environments
    (they may contain deployment credentials), or kill our own process group.
    Re-discover on every pass instead of trusting stale PIDs after reparenting.
    """
    marker = f"{_JOB_ENV}={job_id}"
    groups: set[int] = set()
    if sys.platform == "linux":
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                if marker.encode() not in (entry / "environ").read_bytes().split(b"\0"):
                    continue
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                if fields[0] != "Z":
                    groups.add(int(fields[2]))
            except (OSError, ValueError, IndexError):
                continue
    else:
        output = subprocess.run(
            ["ps", "eww", "-axo", "pid=,pgid=,stat=,command="],
            capture_output=True,
            text=True,
            check=True,
            timeout=3,
        )
        for line in output.stdout.splitlines():
            fields = line.split(None, 3)
            if len(fields) == 4 and marker in fields[3].split() and not fields[2].startswith("Z"):
                groups.add(int(fields[1]))
    return {group for group in groups if group > 1 and group != os.getpgrp()}


async def _reap(process: asyncio.subprocess.Process, job_id: str) -> None:
    # Do not wait for the leader before discovering children: a crash reparents
    # Chromium to init. The inherited marker also locates those orphan sessions.
    try:
        for _ in range(20):
            groups = await asyncio.to_thread(_job_groups, job_id)
            if not groups:
                break
            for group in groups:
                try:
                    os.killpg(group, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            await asyncio.sleep(0.05)
        else:
            raise UpstreamUnavailableError("图表进程清理失败，请重启后端", code="render.cleanup_failed")
    finally:
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        await process.wait()


async def _read_bounded(stream: asyncio.StreamReader, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await stream.read(65536):
        size += len(chunk)
        if size > limit:
            raise UpstreamUnavailableError("图表渲染输出超过限制", code="chart.output_limit")
        chunks.append(chunk)
    return b"".join(chunks)


async def _exchange(process: asyncio.subprocess.Process, payload: bytes) -> bytes:
    stdin, stdout, stderr = process.stdin, process.stdout, process.stderr
    assert stdin and stdout and stderr

    async def write() -> None:
        try:
            stdin.write(payload)
            await stdin.drain()
        finally:
            stdin.close()

    tasks = [
        asyncio.create_task(write()),
        asyncio.create_task(_read_bounded(stdout, _MAX_OUTPUT)),
        asyncio.create_task(_read_bounded(stderr, _MAX_STDERR)),
    ]
    try:
        _, output, _ = await asyncio.gather(*tasks)
        if await process.wait():
            raise UpstreamUnavailableError(
                "图表驱动执行失败，请核查原生镜像架构与浏览器安装", code="chart.worker_failed"
            )
        assert isinstance(output, bytes)
        return output
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def _decode_images(output: bytes) -> tuple[tuple[str, bytes], ...]:
    try:
        entries = json.loads(output)
        if not isinstance(entries, list) or len(entries) > 32:
            raise ValueError("invalid chart list")
        images = []
        for entry in entries:
            if not isinstance(entry, list) or len(entry) != 2:
                raise ValueError("invalid chart entry")
            title, encoded = entry
            if not isinstance(title, str) or not title.strip() or len(title) > 1024 or not isinstance(encoded, str):
                raise ValueError("invalid chart metadata")
            png = base64.b64decode(encoded, validate=True)
            if not png.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("invalid PNG")
            images.append((title, png))
        return tuple(images)
    except (ValueError, TypeError) as exc:
        raise UpstreamUnavailableError("图表渲染未返回有效图片", code="chart.invalid_output") from exc


async def render_chart_pngs(request: dict) -> tuple[tuple[str, bytes], ...]:
    if os.name != "posix":
        # Do not silently fall back to an unkillable thread on unsupported hosts.
        raise UpstreamUnavailableError("图表进程隔离需要 Linux 或 macOS", code="chart.unsupported_platform")
    payload = json.dumps(request, ensure_ascii=False).encode()
    if len(payload) > _MAX_INPUT:
        raise UpstreamUnavailableError("图表输入超过限制", code="chart.input_limit")
    job_id = uuid4().hex
    limiter = _limiter()
    try:
        async with asyncio.timeout(get_settings().pdf_render_timeout_seconds), limiter.slot():
            creation = asyncio.create_task(
                asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "app.infrastructure.chart_worker",
                    cwd=str(Path(__file__).resolve().parents[2]),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    start_new_session=True,
                    env={**os.environ, _JOB_ENV: job_id},
                )
            )
            process = None
            try:
                process = await asyncio.shield(creation)
                return _decode_images(await _exchange(process, payload))
            finally:

                async def cleanup() -> None:
                    child = process if process is not None else await creation
                    try:
                        await _reap(child, job_id)
                    except Exception:
                        limiter.quarantined = True
                        raise

                await wait_for_cleanup(asyncio.create_task(cleanup()))
    except TimeoutError as exc:
        raise UpstreamUnavailableError("图表排队或渲染超时，请稍后重试", code="chart.timeout") from exc
