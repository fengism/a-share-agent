#!/usr/bin/env python3
"""把 HK 全市场历史 K 线（CSV）与除权除息/复权因子导入 market_daily 历史行情库。

数据源（data/data/ 目录，共 3282 只港股）:
  - raw/<code>.csv
      未复权日 K：date,open,close,high,low,volume,amount_est,amount。
      volume 单位为股；amount 为成交额（与库内 sina 快照口径一致，已逐字段比对）。
  - actions/<code>.csv
      除权除息事件（含派息、送股 bonus_ratio、转增 conv_ratio、供股 rights_*）。
      纯回购/其他事件行不导入（不是 category=1 除权除息，且不影响因子口径）。
  - factors/<code>.csv
      前复权仿射因子（date,multiplier,offset），价×mul+offset 口径，
      与 market_daily_adjustment_factors.qfq_* 语义一致（已验证跨除权日连续）。

写入目标:
  - market_daily_bars                 未复权日 K（market='hk'，verification_status='confirmed'）
  - market_corporate_actions          公司行为（category=1 除权除息，原始字段进 raw_json）
  - market_daily_adjustment_factors   逐交易日展开的 qfq 仿射因子

hfq 说明（重要）:
  factors CSV 只有 qfq 因子。实测证明 hfq 无法从 qfq 推导（tdxhub 的 hfq 是锚定到
  "最早事件之前"，而本数据只从 2016-10-03 开始）。因此本脚本把 hfq_multiplier /
  hfq_offset 写为 NULL，并让读取侧在 hfq 请求时回退上游，而不是编造一个近似值。

注意:
  - 因子 CSV 是按除权日的稀疏记录，导入时按"当日取最近一个事件日因子"展开成逐交易日，
    与 A 股库 1:1 对齐（每条 bar 配一条因子）。
  - 名称取自库内已有的港股 sina 快照（2806 只有名字），其余留空。
  - 默认 --on-conflict skip：已存在的键一律保留（流水线写入的行绝不会被覆盖），
    只有同源 hk-csv:* 的行才允许被刷新，换新数据重跑是安全的。
  - 幂等：重复执行按 content_hash 跳过未变化行。

用法（必须用 backend 虚拟环境）:
  backend/.venv/bin/python scripts/init_hk_daily_from_csv.py
  backend/.venv/bin/python scripts/init_hk_daily_from_csv.py --codes 00001,00700
  backend/.venv/bin/python scripts/init_hk_daily_from_csv.py --skip-factors
  backend/.venv/bin/python scripts/init_hk_daily_from_csv.py --on-conflict overwrite
  backend/.venv/bin/python scripts/init_hk_daily_from_csv.py --dry-run --codes 00001
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
import time
from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.modules.market_daily.models import MarketDailyBarRecord
from app.modules.market_daily.paths import MARKET_DAILY_DATABASE_PATH
from app.modules.market_daily.repository import (
    MarketDailyBarRepository,
    _content_hash,
    _provenance_hash,
    _record_hash,
)

DEFAULT_DATA_DIR = Path("data/data")
BAR_SOURCE = "hk-csv:raw"
ACTION_SOURCE = "hk-csv:actions"
FACTOR_SOURCE = "hk-csv:factors"
ALGORITHM_VERSION = "hk-csv-qfq-affine-v1"

_UPSERT_BAR_SQL = """
INSERT INTO market_daily_bars (
    market, instrument_type, code, name, trade_date, currency, open, high, low,
    close, pre_close, change_amount, change_pct, volume, amount, adjustment,
    source, source_quote_time, verification_status, first_refreshed_at,
    last_refreshed_at, revision, data_hash, content_hash, provenance_hash
) VALUES ('hk', 'stock', ?, ?, ?, 'HKD', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'none',
    ?, ?, 'confirmed', ?, ?, 1, ?, ?, ?)
ON CONFLICT(market, instrument_type, code, trade_date, adjustment) DO UPDATE SET
    name=CASE WHEN excluded.name='' THEN market_daily_bars.name ELSE excluded.name END,
    open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close,
    pre_close=excluded.pre_close, change_amount=excluded.change_amount,
    change_pct=excluded.change_pct, volume=excluded.volume, amount=excluded.amount,
    source=excluded.source, source_quote_time=excluded.source_quote_time,
    verification_status='confirmed',
    last_refreshed_at=excluded.last_refreshed_at,
    revision=market_daily_bars.revision + CASE
        WHEN market_daily_bars.content_hash <> excluded.content_hash THEN 1 ELSE 0 END,
    data_hash=excluded.data_hash, content_hash=excluded.content_hash,
    provenance_hash=excluded.provenance_hash
WHERE {conflict_clause}
"""

_SKIP_CONFLICT_CLAUSE = """
    market_daily_bars.source LIKE 'hk-csv:%'
    AND (
        market_daily_bars.content_hash <> excluded.content_hash
        OR market_daily_bars.provenance_hash <> excluded.provenance_hash
    )
"""
_OVERWRITE_CONFLICT_CLAUSE = """
    market_daily_bars.content_hash <> excluded.content_hash
    OR market_daily_bars.provenance_hash <> excluded.provenance_hash
"""

_INSERT_FACTOR_SQL = """
INSERT OR IGNORE INTO market_daily_adjustment_factors (
    market, code, trade_date, qfq_multiplier, qfq_offset,
    hfq_multiplier, hfq_offset, action_hash, algorithm_version, source, calculated_at
) VALUES ('hk', ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)
"""

_INSERT_ACTION_SQL = """
INSERT INTO market_corporate_actions (
    market, code, action_date, sequence, category, category_name,
    cash_dividend, rights_shares, rights_price, bonus_shares, split_ratio,
    raw_json, source, action_hash, refreshed_at
) VALUES ('hk', ?, ?, ?, 1, '除权除息', ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_DELETE_ACTION_SQL = "DELETE FROM market_corporate_actions WHERE market='hk' AND code=?"
_DELETE_FACTOR_SQL = "DELETE FROM market_daily_adjustment_factors WHERE market='hk' AND code=?"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把 HK 全市场历史 K 线 CSV 与除权除息/复权因子导入 market_daily 历史行情库。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="data/data 目录")
    parser.add_argument("--codes", default="", help="逗号分隔的股票代码，默认全部")
    parser.add_argument("--on-conflict", choices=("skip", "overwrite"), default="skip")
    parser.add_argument("--skip-bars", action="store_true", help="跳过日 K 导入")
    parser.add_argument("--skip-factors", action="store_true", help="跳过复权因子导入")
    parser.add_argument("--skip-actions", action="store_true", help="跳过公司行为导入")
    parser.add_argument("--batch-size", type=int, default=20000, help="每批写入行数")
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(8, (os.cpu_count() or 2) // 2)),
        help="按股票并行的线程数（1=串行）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只解析与统计，不写库")
    return parser.parse_args()


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def load_bar_records(path: Path, code: str, name: str) -> list[MarketDailyBarRecord]:
    records: list[MarketDailyBarRecord] = []
    previous: MarketDailyBarRecord | None = None
    clamped = 0
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            close = _float_or_none(row.get("close"))
            trade_date_text = (row.get("date") or "").strip()
            if close is None or close <= 0 or len(trade_date_text) != 10:
                continue
            open_price = _float_or_none(row.get("open"))
            high_price = _float_or_none(row.get("high"))
            low_price = _float_or_none(row.get("low"))
            # CSV 源头有少量自相矛盾的行（如 o=h=l=4.07 但 c=4.08，high 比 close 还低），
            # 模型校验会直接拒绝。high/low 对 tick 级毛刺向 close/open 外扩，
            # 保住这一天的数据，而不是整天丢掉。
            if high_price is not None or low_price is not None:
                high_price = max(v for v in (high_price, open_price, close) if v is not None)
                low_price = min(v for v in (low_price, open_price, close) if v is not None)
                clamped += 1
            record = MarketDailyBarRecord(
                market="hk",
                instrument_type="stock",
                code=code,
                name=name,
                trade_date=trade_date_text,
                currency="HKD",
                open=open_price,
                high=high_price,
                low=low_price,
                close=close,
                volume=_float_or_none(row.get("volume")),
                # amount 是真实成交额；amount_est 是估算列，不用
                amount=_float_or_none(row.get("amount")),
                adjustment="none",
                source=BAR_SOURCE,
            )
            if previous is not None and previous.close > 0:
                record.pre_close = previous.close
                record.change_amount = record.close - previous.close
                record.change_pct = (record.close / previous.close - 1.0) * 100.0
            records.append(record)
            previous = record
    return records


def load_factor_events(path: Path) -> list[tuple[date, float, float]]:
    """读 qfq 仿射因子（date, multiplier, offset）。

    兼容 08133 这类合股股的单列乘性格式（date, factor）：其 factor 本身就是
    乘数（offset=0），qfq = raw × factor，且逐日稠密。
    """
    events: list[tuple[date, float, float]] = []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or ())
        for row in reader:
            day_text = (row.get("date") or "").strip()
            if len(day_text) != 10:
                continue
            if "multiplier" in columns:
                multiplier = _float_or_none(row.get("multiplier"))
                offset = _float_or_none(row.get("offset"))
            else:  # date,factor：合股股的乘性 qfq 因子
                multiplier = _float_or_none(row.get("factor"))
                offset = 0.0 if multiplier is not None else None
            if multiplier is None or offset is None:
                continue
            events.append((date.fromisoformat(day_text), multiplier, offset))
    events.sort(key=lambda item: item[0])
    return events


def expand_factors_to_bars(
    records: list[MarketDailyBarRecord],
    events: list[tuple[date, float, float]],
) -> list[tuple[date, float, float]]:
    """把按除权日的稀疏因子展开到每个交易日：当日取最近一个不晚于当日的事件。

    若某条 bar 早于全部事件，则取最早一条（与 A 股库的起始因子口径一致：
    起始日因子即该区间的锚）。
    """
    if not events:
        return []
    event_dates = [event[0] for event in events]
    expanded: list[tuple[date, float, float]] = []
    for record in records:
        index = bisect_right(event_dates, record.trade_date) - 1
        index = max(index, 0)
        _event_date, multiplier, offset = events[index]
        expanded.append((record.trade_date, multiplier, offset))
    return expanded


def load_action_rows(path: Path, code: str) -> list[dict]:
    """只导入含派息/送股/转增/供股信息的除权除息事件；纯回购等行跳过。"""
    rows: list[dict] = []
    with path.open(newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            day_text = (row.get("date") or "").strip()
            if len(day_text) != 10:
                continue
            dividend = _float_or_none(row.get("div_hkd")) or _float_or_none(row.get("div_orig"))
            bonus = _float_or_none(row.get("bonus_ratio"))
            conv = _float_or_none(row.get("conv_ratio"))
            rights_ratio = _float_or_none(row.get("rights_ratio"))
            rights_price = _float_or_none(row.get("rights_price"))
            if not any(value and value != 0 for value in (dividend, bonus, conv, rights_ratio)):
                continue
            rows.append(
                {
                    "code": code,
                    "action_date": day_text,
                    "sequence": index,
                    "cash_dividend": dividend or 0.0,
                    "rights_shares": rights_ratio or 0.0,
                    "rights_price": rights_price or 0.0,
                    "bonus_shares": bonus or 0.0,
                    "split_ratio": conv or 0.0,
                    "raw_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
                }
            )
    return rows


def _action_hash(rows: list[dict]) -> str:
    payload = json.dumps(
        [
            {
                "action_date": row["action_date"],
                "cash_dividend": row["cash_dividend"],
                "rights_shares": row["rights_shares"],
                "rights_price": row["rights_price"],
                "bonus_shares": row["bonus_shares"],
                "split_ratio": row["split_ratio"],
            }
            for row in rows
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _factor_params(
    code: str,
    expanded: list[tuple[date, float, float]],
    action_hash: str,
    now: str,
) -> list[tuple]:
    return [
        (
            code,
            trade_date.isoformat(),
            multiplier,
            offset,
            action_hash,
            ALGORITHM_VERSION,
            FACTOR_SOURCE,
            now,
        )
        for trade_date, multiplier, offset in expanded
    ]


def _bar_params(record: MarketDailyBarRecord, now: str) -> tuple:
    return (
        record.code,
        record.name,
        record.trade_date.isoformat(),
        record.open,
        record.high,
        record.low,
        record.close,
        record.pre_close,
        record.change_amount,
        record.change_pct,
        record.volume,
        record.amount,
        record.source,
        now,
        now,
        now,
        _record_hash(record),
        _content_hash(record),
        _provenance_hash(record),
    )


def _existing_names(repository: MarketDailyBarRepository) -> dict[str, str]:
    with repository._connect() as connection:
        rows = connection.execute(
            "SELECT DISTINCT code, name FROM market_daily_bars "
            "WHERE market='hk' AND instrument_type='stock' AND name!=''"
        ).fetchall()
    return {str(row["code"]): str(row["name"]) for row in rows}


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir
    raw_dir = data_dir / "raw"
    factors_dir = data_dir / "factors"
    actions_dir = data_dir / "actions"
    if not raw_dir.is_dir():
        raise SystemExit(f"raw 目录不存在: {raw_dir}")

    codes = [code.strip() for code in args.codes.split(",") if code.strip()]
    files = sorted(raw_dir.glob("*.csv"))
    if codes:
        wanted = {f"{code}.csv" for code in codes}
        files = [path for path in files if path.name in wanted]
    if not files:
        raise SystemExit("没有找到任何股票 CSV")

    conflict_clause = (
        _OVERWRITE_CONFLICT_CLAUSE if args.on_conflict == "overwrite" else _SKIP_CONFLICT_CLAUSE
    )
    upsert_sql = _UPSERT_BAR_SQL.format(conflict_clause=conflict_clause)

    repository = MarketDailyBarRepository(MARKET_DAILY_DATABASE_PATH)
    if not args.dry_run:
        repository.initialize()
    names = _existing_names(repository)
    now = datetime.now(UTC).isoformat(timespec="seconds")

    totals = {"stocks": 0, "bars": 0, "bars_written": 0, "factors": 0, "actions": 0, "skipped": 0}
    started_all = time.perf_counter()

    def import_one(path: Path) -> tuple[int, int, int, int, int]:
        """导入单只股票（独立事务），可在线程池里并行。

        每行 K 线/因子要算 3 个 SHA256（content/data/provenance hash），
        单线程全量约 2 小时；按股票拆开后各线程独立连接、独立事务，
        哈希计算天然并行，WAL 写锁只在落盘时短暂互斥。

        多线程并发写会撞 WAL 写锁（默认 busy_timeout 只有 10s，
        高并发下实测会超时报 database is locked），所以拉长到 60s
        并对锁错误按股票重试。
        """
        code = path.stem
        records = load_bar_records(path, code, names.get(code, ""))
        if not records:
            return (0, 0, 0, 0, 1)

        for attempt in range(4):
            try:
                return _import_one_stock(code, records, repository, args, upsert_sql, now)
            except sqlite3.OperationalError as error:
                if "locked" not in str(error).lower() and "busy" not in str(error).lower():
                    raise
                if attempt == 3:
                    raise
                time.sleep(1.5 * (attempt + 1))

        return (0, 0, 0, 0, 0)

    def _import_one_stock(code, records, repository, args, upsert_sql, now):
        with repository._connect() as connection:
            connection.execute("PRAGMA busy_timeout=60000")
            before = connection.total_changes

            if not args.skip_bars and not args.dry_run:
                params = [_bar_params(record, now) for record in records]
                for start in range(0, len(params), args.batch_size):
                    connection.executemany(upsert_sql, params[start : start + args.batch_size])

            action_rows: list[dict] = []
            action_file = actions_dir / f"{code}.csv"
            if action_file.is_file():
                action_rows = load_action_rows(action_file, code)
            if not args.skip_actions and not args.dry_run and action_rows:
                connection.execute(_DELETE_ACTION_SQL, (code,))
                action_hash = _action_hash(action_rows)
                connection.executemany(
                    _INSERT_ACTION_SQL,
                    [
                        (
                            row["code"],
                            row["action_date"],
                            row["sequence"],
                            row["cash_dividend"],
                            row["rights_shares"],
                            row["rights_price"],
                            row["bonus_shares"],
                            row["split_ratio"],
                            row["raw_json"],
                            ACTION_SOURCE,
                            action_hash,
                            now,
                        )
                        for row in action_rows
                    ],
                )
            else:
                action_hash = _action_hash(action_rows)

            factor_rows = 0
            factor_file = factors_dir / f"{code}.csv"
            if factor_file.is_file():
                events = load_factor_events(factor_file)
                expanded = expand_factors_to_bars(records, events)
                factor_rows = len(expanded)
                if not args.skip_factors and not args.dry_run and expanded:
                    connection.execute(_DELETE_FACTOR_SQL, (code,))
                    params = _factor_params(code, expanded, action_hash, now)
                    for start in range(0, len(params), args.batch_size):
                        connection.executemany(
                            _INSERT_FACTOR_SQL, params[start : start + args.batch_size]
                        )

            if not args.dry_run:
                connection.commit()
            changed = connection.total_changes - before

        return (1, len(records), changed, factor_rows, len(action_rows))

    if args.workers <= 1:
        for path in files:
            stocks, bars, written, factors, actions = import_one(path)
            totals["skipped"] += 1 - stocks
            totals["stocks"] += stocks
            totals["bars"] += bars
            totals["bars_written"] += written
            totals["factors"] += factors
            totals["actions"] += actions
            if totals["stocks"] % 200 == 0:
                elapsed = time.perf_counter() - started_all
                print(
                    f"  进度 {totals['stocks']}/{len(files)} 只股票，"
                    f"bars={totals['bars']:,} 因子={totals['factors']:,}  用时 {elapsed:.0f}s",
                    flush=True,
                )
    else:
        done = 0
        failures: list[tuple[str, str]] = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(import_one, path): path for path in files}
            for future in as_completed(futures):
                path = futures[future]
                try:
                    stocks, bars, written, factors, actions = future.result()
                except (sqlite3.Error, OSError, ValueError) as error:
                    # 单只股票失败（脏数据、上游锁超时、行校验等）不能拖垮整个批量导入
                    failures.append((path.stem, f"{type(error).__name__}: {str(error)[:120]}"))
                    print(f"  [失败] {path.stem}: {type(error).__name__}: {str(error)[:120]}", flush=True)
                    stocks, bars, written, factors, actions = 0, 0, 0, 0, 0
                totals["skipped"] += 1 - stocks
                totals["stocks"] += stocks
                totals["bars"] += bars
                totals["bars_written"] += written
                totals["factors"] += factors
                totals["actions"] += actions
                done += 1
                if done % 200 == 0:
                    elapsed = time.perf_counter() - started_all
                    print(
                        f"  进度 {done}/{len(files)} 只股票，"
                        f"bars={totals['bars']:,} 因子={totals['factors']:,}  用时 {elapsed:.0f}s",
                        flush=True,
                    )

    elapsed = time.perf_counter() - started_all
    mode = "dry-run（未写库）" if args.dry_run else args.on_conflict
    print(
        f"\n完成 [{mode}]: {totals['stocks']} 只股票，"
        f"bars {totals['bars']:,} 行（写入变化 {totals['bars_written']:,}），"
        f"因子 {totals['factors']:,} 行，公司行为 {totals['actions']:,} 行，"
        f"跳过空文件 {totals['skipped']} 个，用时 {elapsed:.0f}s"
    )
    if args.workers > 1 and failures:
        print(f"\n失败 {len(failures)} 只（可带 --codes 重跑）:")
        for code, reason in failures[:20]:
            print(f"  {code}: {reason}")
        if len(failures) > 20:
            print(f"  … 以及另外 {len(failures) - 20} 只")
    if not args.dry_run:
        _report()


def _report() -> None:
    import sqlite3

    connection = sqlite3.connect(MARKET_DAILY_DATABASE_PATH)
    try:
        bars = connection.execute(
            "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM market_daily_bars "
            "WHERE market='hk' AND instrument_type='stock'"
        ).fetchone()
        factors = connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT code) FROM market_daily_adjustment_factors "
            "WHERE market='hk'"
        ).fetchone()
        actions = connection.execute(
            "SELECT COUNT(*), COUNT(DISTINCT code) FROM market_corporate_actions WHERE market='hk'"
        ).fetchone()
    finally:
        connection.close()
    print("\n本地 HK 归档:")
    print(f"  bars    {bars[0]:,} 行  {bars[1]} ~ {bars[2]}")
    print(f"  factors {factors[0]:,} 行  覆盖 {factors[1]} 只")
    print(f"  actions {actions[0]:,} 行  覆盖 {actions[1]} 只")


if __name__ == "__main__":
    main()
