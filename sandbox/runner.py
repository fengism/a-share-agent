"""Private, single-worker control plane. Untrusted code ONLY runs in disposable containers."""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Request

log = logging.getLogger(__name__)
LABEL = "a-share.python-sandbox=1"
PREFIX = "a-share-python-"
MAX_CODE_BYTES = 32_768
MAX_OUTPUT_BYTES = 65_536
MAX_CONCURRENT = 2
WALL_SECONDS = 10
TOKEN = os.environ.get("PYTHON_SANDBOX_TOKEN", "")
IMAGE = os.environ.get("PYTHON_SANDBOX_IMAGE", "fengliu1989/a-share-python-sandbox:main")
image_id = ""
healthy = False
dirty: set[str] = set()
jobs: dict[str, asyncio.Task] = {}
# Prevent a delayed POST from starting after DELETE has already arrived.
cancelled: dict[str, float] = {}


class OutputLimitExceeded(Exception):
    pass


async def docker(*args: str, timeout: float = 5) -> tuple[int, bytes, bytes]:
    """Never inherit controller secrets/configuration or accept a Docker command from a request."""
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "--host",
        "unix:///var/run/docker.sock",
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp", "DOCKER_CONFIG": "/nonexistent"},
    )
    total = 0

    async def read(stream: asyncio.StreamReader) -> bytes:
        nonlocal total
        chunks = []
        while chunk := await stream.read(8192):
            total += len(chunk)
            if total > MAX_OUTPUT_BYTES:
                raise OutputLimitExceeded
            chunks.append(chunk)
        return b"".join(chunks)

    assert proc.stdout is not None and proc.stderr is not None
    readers = [asyncio.create_task(read(proc.stdout)), asyncio.create_task(read(proc.stderr))]
    try:
        async with asyncio.timeout(timeout):
            out, err = await asyncio.gather(*readers)
            return await proc.wait(), out, err
    finally:
        for reader in readers:
            reader.cancel()
        if proc.returncode is None:
            with suppress(ProcessLookupError):
                proc.kill()
        await proc.wait()
        await asyncio.gather(*readers, return_exceptions=True)


def create_args(name: str, code: str) -> tuple[str, ...]:
    return (
        "create",
        "--pull=never",
        "--name",
        name,
        "--label",
        LABEL,
        "--network=none",
        "--ipc=private",
        "--cgroupns=private",
        "--hostname=sandbox",
        "--user=65532:65532",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--memory=512m",
        "--memory-swap=512m",
        "--cpus=1",
        "--pids-limit=64",
        "--ulimit=cpu=5:5",
        "--ulimit=nofile=64:64",
        "--ulimit=core=0:0",
        "--ulimit=fsize=16777216:16777216",
        "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=67108864,mode=1777",
        "--workdir=/tmp",
        "--log-driver=none",
        "--restart=no",
        "--init",
        "--env=HOME=/tmp",
        "--env=OPENBLAS_NUM_THREADS=1",
        "--env=OMP_NUM_THREADS=1",
        "--env=MKL_NUM_THREADS=1",
        "--env=NUMEXPR_NUM_THREADS=1",
        "--entrypoint=/usr/local/bin/python",
        image_id,
        "-I",
        "-u",
        "/opt/worker.py",
        code,
    )


async def remove_container(name: str) -> None:
    global healthy
    try:
        status, _, err = await docker("rm", "--force", name)
        if status != 0 and b"No such container" not in err:
            raise RuntimeError("container cleanup failed")
        dirty.discard(name)
    except Exception:
        dirty.add(name)
        healthy = False  # Stop admitting new work until reconciliation succeeds.
        log.error("Sandbox cleanup failed; admission disabled")
        raise


async def run_job(name: str, code: str) -> dict:
    try:
        async with asyncio.timeout(WALL_SECONDS):
            # Complete the create operation before removing by name, including on cancellation.
            creation = asyncio.create_task(docker(*create_args(name, code)))
            try:
                status, _, _ = await asyncio.shield(creation)
            except asyncio.CancelledError:
                with suppress(Exception):
                    await creation
                raise
            if status != 0:
                return failure("隔离环境创建失败；未在本机执行")
            status, stdout, stderr = await docker("start", "--attach", name, timeout=WALL_SECONDS)
            return (
                {
                    "ok": status == 0,
                    "output": stdout.decode("utf-8", errors="replace"),
                    "error": stderr.decode("utf-8", errors="replace") if status else "",
                }
                if status == 0 or stderr
                else failure("Python 执行失败或资源限制触发")
            )
    except TimeoutError:
        return failure("Python 执行超时（最长10秒）")
    except OutputLimitExceeded:
        return failure("Python 输出超过 64 KiB 限制")
    except Exception:
        log.error("Sandbox execution failed")
        return failure("隔离执行服务异常；未在本机执行")
    finally:
        # Removing the container, not just the docker client, kills the entire process tree.
        cleanup = asyncio.create_task(remove_container(name))
        await asyncio.shield(cleanup)


def failure(message: str) -> dict:
    return {"ok": False, "output": "", "error": message}


async def reap_orphans() -> None:
    status, out, _ = await docker("ps", "-a", "--filter", f"label={LABEL}", "--format", "{{.Names}}")
    if status:
        raise RuntimeError("cannot reconcile sandbox containers")
    names = set(out.decode().splitlines()) | dirty
    for name in names:
        if name.startswith(PREFIX) and (name in dirty or name.removeprefix(PREFIX) not in jobs):
            await remove_container(name)


async def reconcile() -> None:
    global healthy
    while True:
        try:
            await reap_orphans()
            healthy = not dirty
        except Exception:
            healthy = False
            log.error("Sandbox reconciliation failed; admission disabled")
        await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global image_id, healthy
    if len(TOKEN) < 32 or not TOKEN.isascii() or not TOKEN.isprintable():
        raise RuntimeError("PYTHON_SANDBOX_TOKEN must contain at least 32 ASCII characters")
    await reap_orphans()
    status, out, _ = await docker("image", "inspect", "--format", "{{json .}}", IMAGE)
    if status:
        raise RuntimeError("Build the dedicated sandbox image before starting the runner")
    image = json.loads(out)
    if image.get("Config", {}).get("Volumes") or not re.fullmatch(r"sha256:[0-9a-f]{64}", image["Id"]):
        raise RuntimeError("Sandbox image must not define volumes")
    image_id = image["Id"]  # Pin all jobs to the inspected image, not a mutable tag.
    healthy = True
    reaper = asyncio.create_task(reconcile())
    try:
        yield
    finally:
        healthy = False
        reaper.cancel()
        with suppress(asyncio.CancelledError):
            await reaper
        active = list(jobs.values())
        for task in active:
            if not task.cancelling():
                task.cancel()
        await asyncio.gather(*active, return_exceptions=True)
        jobs.clear()
        await reap_orphans()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def authorize(request: Request, job_id: str) -> None:
    if not TOKEN or not hmac.compare_digest(
        request.headers.get("authorization", "").encode(), f"Bearer {TOKEN}".encode()
    ):
        raise HTTPException(401, "Unauthorized")
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        raise HTTPException(400, "Invalid job id")
    now = time.monotonic()
    for key, expires in list(cancelled.items()):
        if expires <= now:
            del cancelled[key]


@app.get("/health")
async def health():
    if not healthy:
        raise HTTPException(503, "Unavailable")
    return {"ok": True}


@app.post("/jobs/{job_id}")
async def execute(job_id: str, request: Request):
    authorize(request, job_id)
    if not healthy:
        raise HTTPException(503, "Unavailable")
    if len(jobs) >= MAX_CONCURRENT or len(cancelled) >= 512:
        raise HTTPException(429, "Busy")
    payload = bytearray()
    try:
        async with asyncio.timeout(3):
            async for chunk in request.stream():
                if len(payload) + len(chunk) > MAX_CODE_BYTES * 6 + 64:
                    raise HTTPException(413, "Code too large")
                payload.extend(chunk)
    except TimeoutError:
        raise HTTPException(408, "Request body timed out") from None
    try:
        data = json.loads(payload)
        if not isinstance(data, dict) or set(data) != {"code"}:
            raise ValueError
        code = data["code"]
        if (
            not isinstance(code, str)
            or not code.strip()
            or "\x00" in code
            or len(code.encode("utf-8")) > MAX_CODE_BYTES
        ):
            raise ValueError
    except (ValueError, UnicodeError):
        raise HTTPException(400, "Invalid code") from None
    # Recheck after streaming the request, before any await or container creation.
    if not healthy or len(jobs) >= MAX_CONCURRENT:
        raise HTTPException(429, "Busy")
    if job_id in cancelled or job_id in jobs:
        raise HTTPException(409, "Job already used or cancelled")
    task = asyncio.create_task(run_job(PREFIX + job_id, code))
    jobs[job_id] = task
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=0.1)
            if await request.is_disconnected():
                if not task.cancelling():
                    task.cancel()
                break
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        if not task.cancelling():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.shield(task)
        return failure("Python 任务已取消")
    except Exception:
        return failure("隔离服务清理失败，已暂停新任务")
    finally:
        jobs.pop(job_id, None)
        cancelled[job_id] = time.monotonic() + 60


@app.delete("/jobs/{job_id}")
async def cancel(job_id: str, request: Request):
    authorize(request, job_id)
    if len(cancelled) >= 512 and job_id not in cancelled:
        raise HTTPException(429, "Busy")
    cancelled[job_id] = time.monotonic() + 60
    task = jobs.get(job_id)
    if task is not None:
        if not task.cancelling():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await asyncio.shield(task)
    return {"ok": True}
