"""版本检查逻辑测试：sha 版本对比与 Hub 响应解析。"""

from __future__ import annotations

import asyncio

import pytest

from app.api import version


def test_pick_latest_sha_tag() -> None:
    tags = [
        {"name": "main"},
        {"name": "sha-def5678adbc"},
        {"name": "sha-abc1234ffff"},
        {"name": "v1.0"},
    ]
    assert version._pick_latest_sha_tag(tags) == "def5678adbc"


def test_pick_latest_sha_tag_empty() -> None:
    assert version._pick_latest_sha_tag([]) is None
    assert version._pick_latest_sha_tag([{"name": "main"}]) is None


@pytest.mark.asyncio
async def test_version_check_update_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_VERSION", "abc1234ffff")
    version._cache["at"] = 0.0
    version._cache["latest"] = None
    monkeypatch.setattr(
        version, "fetch_latest_version", _fake_fetch("abc1234abcd")
    )
    data = await version.version_check()
    assert data.current_version == "abc1234ffff"
    assert data.latest_version == "abc1234abcd"
    assert data.update_available is False  # 同一个 commit 的 short sha


@pytest.mark.asyncio
async def test_version_check_no_update(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_VERSION", "abc1234ffff")
    version._cache["at"] = 0.0
    monkeypatch.setattr(version, "fetch_latest_version", _fake_fetch("def5678abcd"))
    data = await version.version_check()
    assert data.update_available is True


@pytest.mark.asyncio
async def test_version_check_hub_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_VERSION", "abc1234ffff")
    version._cache["at"] = 0.0
    monkeypatch.setattr(version, "fetch_latest_version", _fake_fetch(None))
    data = await version.version_check()
    assert data.latest_version is None
    assert data.update_available is False


def _fake_fetch(latest: str | None):
    async def _fetch() -> str | None:
        return latest

    return _fetch
