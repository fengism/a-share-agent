"""Shared browser launch policy for the backend runtime."""

from collections.abc import Mapping, Sequence
from typing import Any

FULL_CHROMIUM_CHANNEL = "chromium"


async def launch_full_chromium(
    browser_type: Any,
    *,
    args: Sequence[str],
    proxy: Mapping[str, str] | None = None,
) -> Any:
    """Launch the installed full Chromium binary in headless mode.

    Explicitly selecting the ``chromium`` channel prevents Playwright from
    falling back to its separate headless-shell artifact. The Docker image can
    therefore install Chromium with ``--no-shell``.
    """
    options: dict[str, Any] = {
        "channel": FULL_CHROMIUM_CHANNEL,
        "headless": True,
        "args": list(args),
    }
    if proxy is not None:
        options["proxy"] = dict(proxy)
    return await browser_type.launch(**options)
