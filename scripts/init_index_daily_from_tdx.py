#!/usr/bin/env python3
"""把 A 股指数 10 年日 K 一次性导入 market_daily 历史行情库。

为什么需要单独脚本：
* Fuyao 全市场 dump 只有个股（10,316,588 行与本地 cn/stock 完全一致），不含指数。
* ``/api/market/index-kline`` 已经在读 ``load_local_daily_kline(instrument_type="index")``，
  但本地一张 A 股指数行都没有，所以每次都回落��游。
* 指数没有复权概念（``adjustment`` 恒为 ``none``），也不需要复权因子表。

数据源：TDX 本地接口，单次上限 800 根（约 3.2 年），靠 ``start`` 向前翻页。
首页约 3.7s（要下全量本地数据），后续每页约 120ms，因此整段十年约 4s/指数。

写入目标与个股导入完全一致：
  - market_daily_bars（instrument_type='index'，verification_status='confirmed'）
  - 同一套 data_hash / content_hash / provenance_hash 口径，revision 仅在内容变化时累加

注意：
  - 默认 --on-conflict skip：只补空缺；只有同为 ``index-tdx:*`` 来源的行才允许刷新，
    换新 TDX 数据重跑是安全的。``--on-conflict overwrite`` 才会覆盖已有行。
  - 幂等：重复执行按 content_hash 跳过未变化行。

用法（必须用 backend 虚拟环境）:
  backend/.venv/bin/python scripts/init_index_daily_from_tdx.py
  backend/.venv/bin/python scripts/init_index_daily_from_tdx.py --codes 000001,399001
  backend/.venv/bin/python scripts/init_index_daily_from_tdx.py --dry-run
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from datetime import UTC, datetime
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

# 应用实际会用到的宽基指数（市场页指数卡 + 顶栏 ticker + 量化基准）
DEFAULT_INDEX_CODES = (
    "000001",  # 上证指数
    "399001",  # 深证成指
    "399006",  # 创业板指
    "000688",  # 科创50
    "000300",  # 沪深300
    "000905",  # 中证500
    "000852",  # 中证1000
    "899050",  # 北证50
)

INDEX_NAMES = {
    "000001": "上证指数",
    "399001": "深证成指",
    "399006": "创业板指",
    "000688": "科创50",
    "000300": "沪深300",
    "000905": "中证500",
    "000852": "中证1000",
    "899050": "北证50",
}

SOURCE = "index-tdx:kline"
#: TDX 单次返回上限
TDX_PAGE_SIZE = 800
#: 默认起始日期（约 10 年）
DEFAULT_START_DATE = "2016-01-01"

_UPSERT_BAR_SQL = """
INSERT INTO market_daily_bars (
    market, instrument_type, code, name, trade_date, currency, open, high, low,
    close, pre_close, change_amount, change_pct, volume, amount, adjustment,
    source, source_quote_time, verification_status, first_refreshed_at,
    last_refreshed_at, revision, data_hash, content_hash, provenance_hash
) VALUES (?, 'index', ?, ?, ?, 'CNY', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'none',
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
    market_daily_bars.source LIKE 'index-tdx:%'
    AND (
        market_daily_bars.content_hash <> excluded.content_hash
        OR market_daily_bars.provenance_hash <> excluded.provenance_hash
    )
"""
_OVERWRITE_CONFLICT_CLAUSE = """
    market_daily_bars.content_hash <> excluded.content_hash
    OR market_daily_bars.provenance_hash <> excluded.provenance_hash
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把 TDX 指数 10 年日 K 导入 market_daily 历史行情库。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--codes",
        default=",".join(DEFAULT_INDEX_CODES),
        help="逗号分隔的指数代码",
    )
    parser.add_argument("--start-date", default=DEFAULT_START_DATE, help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end-date", default="", help="结束日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--on-conflict", choices=("skip", "overwrite"), default="skip")
    parser.add_argument("--dry-run", action="store_true", help="只抓取与统计，不写库")
    parser.add_argument("--max-pages", type=int, default=8, help="每个指数最多翻多少页 800 根")
    return parser.parse_args()


def fetch_index_pages(symbol: str, *, max_pages: int) -> list[dict]:
    """从 TDX 向前翻页取指数日 K，直到取空或达到 max_pages。

    TDX 的分页是"start 越大数据越旧"，而**页内按日期升序**。所以要拿到全局升序，
    只能倒转页序、保留页内顺序；对整个列表做reverse 会把页内也倒过来，
    拼出来的序列变成"旧→新→更旧→更新"，首尾日期完全错位。
    """
    from app.infrastructure.providers.registry import get_provider

    provider = get_provider("tdxhub")
    normalized = provider._normalize_index_request(symbol)
    pages: list[list[dict]] = []
    for page in range(max_pages):
        frame = provider._quotes.call(
            "index",
            symbol=normalized,
            frequency=provider.DAILY_FREQUENCY,
            start=page * TDX_PAGE_SIZE,
            offset=TDX_PAGE_SIZE,
        )
        if frame is None or len(frame) == 0:
            break
        pages.append(frame.to_dict("records"))
        if len(frame) < TDX_PAGE_SIZE:
            break
    return [row for page in reversed(pages) for row in page]


def _to_bar_record(row: dict, code: str, name: str, start_date: str) -> MarketDailyBarRecord | None:
    raw_date = str(row.get("datetime") or row.get("date") or "")
    text = raw_date[:10].replace("/", "-")
    if len(text) != 10 or text < start_date:
        return None
    close = _float_or_none(row.get("close"))
    if close is None or close <= 0:
        return None
    volume = _float_or_none(row.get("volume"))
    return MarketDailyBarRecord(
        market="cn",
        instrument_type="index",
        code=code,
        name=name,
        trade_date=text,
        currency="CNY",
        open=_float_or_none(row.get("open")),
        high=_float_or_none(row.get("high")),
        low=_float_or_none(row.get("low")),
        close=close,
        pre_close=_float_or_none(row.get("pre_close")),
        change_amount=_float_or_none(row.get("change_amt")),
        change_pct=_float_or_none(row.get("change_pct")),
        # TDX 指数成交量单位是"手"，库内存"股"
        volume=volume * 100 if volume is not None else None,
        amount=_float_or_none(row.get("amount")),
        adjustment="none",
        source=SOURCE,
        source_quote_time=None,
    )


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number


def _derive_pre_close(records: list[MarketDailyBarRecord]) -> None:
    """按相邻交易日收盘价推导 pre_close / change_amount / change_pct。

    TDX 底层接口只给 OHLCV+amount，不给昨收与涨跌幅；provider 的
    ``fetch_index_kline`` 是在返回前用 ``_format_index_kline_df`` 补的。
    本脚本直接写库、绕过了那一步，若不补齐，指数 K 线读本地后
    ``change_pct``/``pre_close`` 会全变 NULL（K 线 HUD 与涨跌幅列会跟着空掉）。
    """
    previous: MarketDailyBarRecord | None = None
    for record in records:
        if previous is None:
            previous = record
            continue
        pre_close = previous.close
        record.pre_close = pre_close
        record.change_amount = record.close - pre_close
        record.change_pct = (record.close / pre_close - 1.0) * 100.0 if pre_close > 0 else None
        previous = record


def main() -> None:
    args = parse_args()
    codes = [code.strip() for code in args.codes.split(",") if code.strip()]
    start_date = args.start_date
    end_date = args.end_date or datetime.now(UTC).date().isoformat()
    conflict_clause = (
        _OVERWRITE_CONFLICT_CLAUSE if args.on_conflict == "overwrite" else _SKIP_CONFLICT_CLAUSE
    )
    sql = _UPSERT_BAR_SQL.format(conflict_clause=conflict_clause)

    repository = MarketDailyBarRepository(MARKET_DAILY_DATABASE_PATH)
    if not args.dry_run:
        repository.initialize()

    total_inserted = 0
    total_changed = 0
    now = datetime.now(UTC).isoformat(timespec="seconds")

    for code in codes:
        name = INDEX_NAMES.get(code, "")
        started = time.perf_counter()
        rows = fetch_index_pages(code, max_pages=args.max_pages)
        records = [
            record
            for record in (_to_bar_record(row, code, name, start_date) for row in rows)
            if record is not None
        ]
        records = [r for r in records if r.trade_date.isoformat() <= end_date]
        if records:
            _derive_pre_close(records)
        if not records:
            print(f"  {code} {name}: 无数据")
            continue

        span = f"{records[0].trade_date}~{records[-1].trade_date}"
        if args.dry_run:
            print(f"  {code} {name}: {len(records)} 行 {span}（dry-run 不写库）")
            total_inserted += len(records)
            continue

        with repository._connect() as connection:
            before = connection.total_changes
            connection.executemany(sql, [_bar_params(record, now) for record in records])
            connection.commit()
            affected = connection.total_changes - before
        total_inserted += len(records)
        total_changed += affected
        elapsed = (time.perf_counter() - started) * 1000
        print(
            f"  {code} {name}: {len(records)} 行 {span} 写入 {affected} 行  {elapsed:.0f}ms"
        )

    print(f"\n合计: 抓取 {total_inserted} 行，实际写入/更新 {total_changed} 行")
    if not args.dry_run:
        _report()


def _bar_params(record: MarketDailyBarRecord, now: str) -> tuple:
    """按 _UPSERT_BAR_SQL 的列顺序绑定；market/instrument_type 在 SQL 里是字面量。"""
    return (
        "cn",
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


def _report() -> None:
    connection = sqlite3.connect(MARKET_DAILY_DATABASE_PATH)
    try:
        rows = connection.execute(
            "SELECT code, name, COUNT(*), MIN(trade_date), MAX(trade_date) "
            "FROM market_daily_bars WHERE market='cn' AND instrument_type='index' "
            "GROUP BY code, name ORDER BY code"
        ).fetchall()
    finally:
        connection.close()
    print("\n本地 A 股指数归档：")
    for code, name, count, first, last in rows:
        print(f"  {code} {name or '-':8s} {count:5d} 行  {first} ~ {last}")


if __name__ == "__main__":
    main()