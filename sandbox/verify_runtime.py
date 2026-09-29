"""CI only: exercise actual worker creation, resource limits, cancellation and cleanup."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

import runner


async def job(code: str) -> dict[str, Any]:
    identifier = uuid4().hex
    task: asyncio.Task[dict[str, Any]] = asyncio.create_task(runner.run_job(runner.PREFIX + identifier, code))
    runner.jobs[identifier] = task
    try:
        return await task
    finally:
        runner.jobs.pop(identifier, None)


async def main() -> None:
    async with runner.lifespan(runner.app):
        result = await job(
            "import os,platform,json; "
            "assert os.getuid() == 65532; "
            "assert np.array([1,2]).sum() == 3; "
            "assert pd.DataFrame({'x':[1,2]}).x.sum() == 3; "
            "print(json.dumps({'arch':platform.machine(),'uid':os.getuid()}))"
        )
        if not result.get("ok"):
            raise AssertionError(f"Native sandbox execution failed: {result}")
        print("sandbox native execution:", result["output"].strip())
        # Validate the production policy, not a permissive docker run substitute.
        identifier = uuid4().hex
        name = runner.PREFIX + identifier
        reservation = asyncio.create_task(asyncio.Event().wait())
        runner.jobs[identifier] = reservation
        try:
            status, _, _ = await runner.docker(*runner.create_args(name, "print('ok')"))
            assert status == 0
            status, out, _ = await runner.docker("inspect", name)
            assert status == 0
            container = json.loads(out)[0]
            host = container["HostConfig"]
            assert host["NetworkMode"] == "none" and host["ReadonlyRootfs"]
            assert host["Memory"] == 512 * 1024 * 1024 and host["PidsLimit"] == 64
            assert container["Config"]["User"] == "65532:65532"
            assert not container["Mounts"] or all(m["Type"] == "tmpfs" for m in container["Mounts"])
        finally:
            await runner.remove_container(name)
            reservation.cancel()
            await asyncio.gather(reservation, return_exceptions=True)
            runner.jobs.pop(identifier, None)
        # Cancellation must remove the actual worker, not just cancel docker CLI.
        identifier = uuid4().hex
        name = runner.PREFIX + identifier
        task = asyncio.create_task(runner.run_job(name, "import time; time.sleep(60)"))
        runner.jobs[identifier] = task
        try:
            async with asyncio.timeout(5):
                while True:
                    status, _, _ = await runner.docker("inspect", name)
                    if status == 0:
                        break
                    await asyncio.sleep(0.1)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            status, _, _ = await runner.docker("inspect", name)
            assert status != 0, "Cancelled worker was not removed"
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            runner.jobs.pop(identifier, None)
            await runner.remove_container(name)
    print("sandbox lifecycle, limits and cancellation smoke passed")


if __name__ == "__main__":
    asyncio.run(main())
