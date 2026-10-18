"""文件型快照与嵌套归档的保留清理测试。"""

from __future__ import annotations

import os
from pathlib import Path

from app.infrastructure.persistence.file_retention import purge_old_files


def _write_with_age(directory: Path, name: str, age_days: float, now: float) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    timestamp = now - age_days * 24 * 60 * 60
    os.utime(path, (timestamp, timestamp))
    return path


def test_purge_old_files_removes_only_expired(tmp_path: Path) -> None:
    now = 1_700_000_000.0
    old = _write_with_age(tmp_path, "old.json", age_days=100, now=now)
    fresh = _write_with_age(tmp_path, "fresh.json", age_days=1, now=now)

    deleted = purge_old_files(tmp_path, keep_days=30, now=now)

    assert deleted == 1
    assert not old.exists()
    assert fresh.exists()


def test_purge_old_files_skips_non_positive_keep_days(tmp_path: Path) -> None:
    now = 1_700_000_000.0
    old = _write_with_age(tmp_path, "old.json", age_days=100, now=now)

    assert purge_old_files(tmp_path, keep_days=0, now=now) == 0
    assert old.exists()


def test_purge_expired_file_data_covers_snapshots_and_archives(tmp_path: Path, monkeypatch) -> None:
    from app.configuration import paths
    from app.modules.analysis.persistence import repository as analysis_repository
    from app.modules.industry_chain.persistence import repository as industry_chain_repository
    from app.runtime import maintenance

    now = 1_700_000_000.0
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    monkeypatch.setattr(analysis_repository, "_DATA_DIR", tmp_path / "analyses")
    monkeypatch.setattr(industry_chain_repository, "_DATA_DIR", tmp_path / "industry_chains")
    monkeypatch.setattr(analysis_repository, "rebuild_analysis_history_index", lambda: None)
    monkeypatch.setattr(industry_chain_repository, "rebuild_industry_chain_history_index", lambda: None)

    for name in ("potential_stocks", "potential_performance"):
        _write_with_age(tmp_path / name, "2025-01-01.json", age_days=400, now=now)
        _write_with_age(tmp_path / name, "2026-01-01.json", age_days=1, now=now)
    _write_with_age(tmp_path / "valuation_snapshots", "600519.json", age_days=100, now=now)
    _write_with_age(tmp_path / "valuation_snapshots", "000001.json", age_days=1, now=now)

    _write_with_age(tmp_path / "analyses" / "users" / "1" / "600519", "2025-01-01.json", age_days=400, now=now)
    _write_with_age(tmp_path / "analyses" / "000001", "2025-01-01.json", age_days=1, now=now)
    _write_with_age(tmp_path / "industry_chains" / "old-theme", "old.json", age_days=400, now=now)
    _write_with_age(tmp_path / "industry_chains" / "new-theme", "new.json", age_days=1, now=now)

    purged = maintenance.purge_expired_file_data(
        potential_retention_days=180,
        valuation_snapshot_retention_days=30,
        analysis_archive_retention_days=90,
        industry_chain_retention_days=90,
        now=now,
    )

    assert purged["potential_stocks"] == 1
    assert purged["potential_performance"] == 1
    assert purged["valuation_snapshots"] == 1
    assert purged["analysis_archives"] == 1
    assert purged["industry_chain_archives"] == 1
    assert (tmp_path / "potential_stocks" / "2026-01-01.json").exists()
    assert (tmp_path / "valuation_snapshots" / "000001.json").exists()
    assert (tmp_path / "analyses" / "000001").exists()
    assert (tmp_path / "industry_chains" / "new-theme").exists()
    assert not (tmp_path / "analyses" / "users" / "1" / "600519").exists()
    assert not (tmp_path / "industry_chains" / "old-theme").exists()
