"""每小时名录同步必须把名称映射一起更新。

此前 `stock_names.json` 只由启动预热（`supervised_once`，只跑一次）写入，
每小时的 `sync_exchange_master_data()` 只更新数据库名录、不回写名称文件；而内存里的
名称/简称/拼音索引只在文件签名变化时重建。两者叠加的后果：长跑进程里新上市股票的
名称永远认不出来，只能靠股票代码。

注意：`refresh_industry_mapping_file_daily()` 结尾是 `run_periodic(...)` 无限循环，
测试必须截获 `coro_factory` 只跑一次迭代，不能直接 await 整个任务。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.runtime import background_tasks


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail: dict[str, BaseException] = {}

    def factory(self, name: str, *, result: Any = None):
        async def _run(*args: object, **kwargs: object):
            self.calls.append(name)
            error = self.fail.get(name)
            if error is not None:
                raise error
            return result

        return _run


class _IndustryResult:
    added = 0
    updated = 0
    unchanged = 0


class _SyncResult:
    added = 0
    updated = 0
    unchanged = 0
    skipped = 0


class _EnrichResult(dict):
    pass


def _patch(monkeypatch: pytest.MonkeyPatch, recorder: _Recorder) -> None:
    # 任务体在函数内部做 `from X import Y`，所以 patch 到 public 模块的属性上。
    import app.financial_data.stock.public as stock_public
    import app.modules.industry_classification.public as classification_public
    import app.modules.stock_concept.public as concept_public
    import app.modules.stock_profile.public as profile_public

    monkeypatch.setattr(
        classification_public, "scheduled_refresh",
        recorder.factory("industry", result=_IndustryResult()),
    )
    monkeypatch.setattr(
        profile_public, "sync_exchange_master_data",
        recorder.factory("master_sync", result=_SyncResult()),
    )
    monkeypatch.setattr(
        profile_public, "auto_enrich_pending_profiles",
        recorder.factory("profile_enrich", result=_EnrichResult(enriched=0)),
    )
    monkeypatch.setattr(stock_public, "build_stock_name_map", recorder.factory("name_map"))
    monkeypatch.setattr(
        concept_public, "auto_enrich_pending_concepts",
        recorder.factory("concept_enrich", result=_EnrichResult(enriched=0)),
    )


async def _run_one_iteration(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def _fake_run_periodic(*, name, coro_factory, interval_seconds, leader_election=False):
        captured["name"] = name
        captured["factory"] = coro_factory

    monkeypatch.setattr(background_tasks.task_scheduler, "run_periodic", _fake_run_periodic)
    await background_tasks.refresh_industry_mapping_file_daily()
    await captured["factory"]()


@pytest.mark.asyncio
async def test_name_map_is_refreshed_after_the_exchange_master_sync(monkeypatch):
    recorder = _Recorder()
    _patch(monkeypatch, recorder)

    await _run_one_iteration(monkeypatch)

    assert "master_sync" in recorder.calls
    assert "name_map" in recorder.calls, "名录同步后必须联动更新名称映射"
    assert recorder.calls.index("name_map") > recorder.calls.index("master_sync")


@pytest.mark.asyncio
async def test_name_map_failure_does_not_break_the_rest_of_the_task(monkeypatch):
    recorder = _Recorder()
    _patch(monkeypatch, recorder)
    recorder.fail["name_map"] = RuntimeError("upstream down")

    await _run_one_iteration(monkeypatch)

    # 名称映射失败不能拖垮后续的资料/概念补充
    assert "profile_enrich" in recorder.calls
    assert "concept_enrich" in recorder.calls


@pytest.mark.asyncio
async def test_name_map_is_skipped_when_the_master_sync_fails(monkeypatch):
    recorder = _Recorder()
    _patch(monkeypatch, recorder)
    recorder.fail["master_sync"] = RuntimeError("exchange down")

    await _run_one_iteration(monkeypatch)

    # 名录同步失败不阻断名称映射对齐（它复用 24h 缓存的名录）与后续跑批。
    assert "name_map" in recorder.calls
    assert "profile_enrich" in recorder.calls


@pytest.mark.asyncio
async def test_name_map_is_refreshed_even_when_the_weekly_industry_update_is_not_due(monkeypatch):
    """行业是周更，名称映射必须每小时对齐一次——否则新股要等一周才被认出来。"""
    recorder = _Recorder()
    _patch(monkeypatch, recorder)
    import app.modules.industry_classification.public as classification_public

    # scheduled_refresh 返回 None 表示本周的行业更新还没到期
    monkeypatch.setattr(
        classification_public, "scheduled_refresh", recorder.factory("industry", result=None),
    )

    await _run_one_iteration(monkeypatch)

    assert "master_sync" not in recorder.calls
    assert "name_map" in recorder.calls, "名称映射不能绑在行业周更上"
