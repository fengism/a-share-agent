"""CI-only startup/readiness smoke; never run against an existing database."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

_DB_SUFFIXES = (".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3")
_ERROR_TYPE = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception))(?::|$)", re.MULTILINE)


def require_empty_database_dir(data: Path) -> None:
    # Actual databases live in data/db, not directly beneath data. Refuse links
    # too: an apparently empty test directory must not redirect into live data.
    if data.is_symlink() or (data.exists() and not data.is_dir()):
        raise RuntimeError("Startup smoke requires a real ephemeral data directory")
    if any(parent.is_symlink() for parent in data.parents):
        raise RuntimeError("Startup smoke data directory must not traverse symlinks")
    for path in data.rglob("*"):
        if path.is_symlink() or path.name.lower().endswith(_DB_SUFFIXES):
            raise RuntimeError("Startup smoke requires an empty ephemeral database directory")


def safe_readiness_summary(payload: object) -> dict:
    if not isinstance(payload, dict):
        return {"response": "invalid"}
    states = {"ok", "error", "connected", "unknown", "starting", "running", "stopped", "waiting", "idle"}

    def state(value):
        return value if isinstance(value, str) and value in states else "unknown"

    tasks = payload.get("background_tasks")
    counts: dict[str, int] = {}
    if isinstance(tasks, dict):
        for task in tasks.values():
            status = state(task.get("status")) if isinstance(task, dict) else "unknown"
            counts[status] = counts.get(status, 0) + 1
    return {"status": state(payload.get("status")), "database": state(payload.get("database")), "task_states": counts}


def failure_diagnostics(log_path: Path, readiness: object, returncode: int | None) -> str:
    # Never copy raw startup logs into CI output: first startup prints an admin
    # password and provider exceptions can contain credentials. Categories only.
    with log_path.open("rb") as logs:
        logs.seek(max(0, log_path.stat().st_size - 65536))
        tail = logs.read(65536).decode("utf-8", errors="replace")
    errors = sorted(set(_ERROR_TYPE.findall(tail)))[:8]
    return json.dumps(
        {"exit_code": returncode, "exception_types": errors, "readiness": safe_readiness_summary(readiness)}
    )


def main() -> None:
    data = Path(os.environ["APP_DATA_DIR"])
    require_empty_database_dir(data)
    with tempfile.TemporaryDirectory(prefix="application-smoke-") as directory:
        log_path = Path(directory) / "startup.log"
        with log_path.open("wb") as logs:
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "18000"],
                stdout=logs,
                stderr=subprocess.STDOUT,
            )
            readiness = None
            try:
                deadline = time.monotonic() + 120
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("Application exited during startup")
                    try:
                        with opener.open("http://127.0.0.1:18000/api/health/ready", timeout=2) as response:
                            readiness = json.load(response)
                        if readiness.get("database") == "connected" and readiness.get("status") == "ok":
                            if not readiness.get("background_tasks"):
                                raise AssertionError("Background tasks were not registered")
                            print("application startup, database and background readiness passed")
                            return
                    except urllib.error.HTTPError as exc:
                        try:
                            readiness = json.loads(exc.read(65536))
                        except ValueError:
                            readiness = None
                        finally:
                            exc.close()
                    except (urllib.error.URLError, TimeoutError):
                        pass
                    time.sleep(0.5)
                raise TimeoutError("Application did not become ready within 120 seconds")
            except Exception:
                logs.flush()
                print(
                    "Startup diagnostics: " + failure_diagnostics(log_path, readiness, process.poll()), file=sys.stderr
                )
                raise
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
