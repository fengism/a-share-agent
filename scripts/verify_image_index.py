"""Reject single-arch or ambiguous image indexes before publishing public tags."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def verify_image_index(index: dict[str, Any]) -> None:
    platforms: list[tuple[str, str]] = []
    for manifest in index.get("manifests", []):
        platform = manifest.get("platform", {})
        os_name, arch = platform.get("os"), platform.get("architecture")
        if (os_name, arch) == ("unknown", "unknown"):
            continue  # BuildKit provenance/SBOM manifests are not runnable images.
        if os_name != "linux" or arch not in {"amd64", "arm64"}:
            raise ValueError(f"Unsupported image platform: {platform!r}")
        platforms.append((os_name, arch))
    if sorted(platforms) != [("linux", "amd64"), ("linux", "arm64")]:
        raise ValueError(f"Expected exactly linux/amd64 + linux/arm64, got {platforms!r}")


if __name__ == "__main__":
    verify_image_index(json.loads(Path(sys.argv[1]).read_text()))
    print("verified linux/amd64 + linux/arm64 image index")
