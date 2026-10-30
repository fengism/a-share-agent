"""概念板块联动：概念成分股（含实时行情）与本地合成的等权指数。

数据全部来自本地，不依赖上游：

* 概念↔成分股映射来自 ``industry_data.db`` 的 ``stock_concept_mappings``
  （iwencai 全A 导入，含每只股票的完整概念标签，用于反向联动）。
* 指数由 :mod:`app.modules.market_daily.concept_index` 用本地前复权日线合成。
* 成分股行情复用 :func:`app.financial_data.stock.quotes.realtime.fetch_realtime_quote_set`，
  与个股页同一套 tencent→tdxhub→fuyao 兜底链。
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.cache import market_cache as cache
from app.core.cache_policies import CONCEPT_LINKAGE
from app.core.exceptions import InvalidRequestError, ResourceNotFoundError
from app.core.market import market_today, normalize_code, safe_float
from app.core.timezones import SHANGHAI_TIMEZONE
from app.financial_data.stock.quotes.realtime import fetch_realtime_quote_set
from app.infrastructure.persistence.connection import get_connection
from app.modules.market_daily.concept_index import load_concept_index, sample_constituents
from app.modules.market_daily.service import market_daily_bar_service

logger = logging.getLogger(__name__)

#: 相关概念（与当前概念成分股重叠最多）返回条数。
RELATED_CONCEPT_LIMIT = 12

#: 相关概念的规模上限倍数（相对当前概念成分股数）。融资融券、深股通这类
#: 普适属性概念对任何题材都能重叠 40%+，不设约束会永远霸榜，把真正的
#: 题材关联（如 人形机器人↔机器人概念）挤到下面去。
RELATED_MAX_SIZE_RATIO = 2.0

#: 成分股实时行情拉取超时时间（秒），防止上游多批串行或异常时拖死整个接口。
QUOTE_FETCH_TIMEOUT_SECONDS = 6.0


#: 指数合成的最大回溯天数（约 10 年，与本地日线覆盖一致）。
MAX_INDEX_DAYS = 3650


@dataclass(frozen=True)
class ConceptSummary:
    name: str
    stock_count: int
    change_pct: float | None = None
    change_date: str | None = None
    up_count: int | None = None
    down_count: int | None = None
    limit_up_count: int | None = None
    sample_count: int | None = None


@dataclass(frozen=True)
class ConceptDailyChange:
    """某个概念的最近一个交易日等权涨跌聚合（口径与合成指数一致）。"""

    date: str
    change_pct: float
    up_count: int
    down_count: int
    limit_up_count: int
    sample_count: int


@dataclass(frozen=True)
class ConceptConstituent:
    code: str
    name: str
    concepts: list[str]


@dataclass(frozen=True)
class RelatedConcept:
    """与当前概念成分股重叠最多的其他概念。"""

    name: str
    overlap: int
    ratio: float


def _industry_connection() -> sqlite3.Connection:
    return get_connection("industry")


def _market_daily_connection() -> sqlite3.Connection:
    return get_connection("market_daily")


def list_concepts(*, query: str = "", limit: int = 200, order: str = "size") -> list[ConceptSummary]:
    """概念列表，附带最近交易日等权涨跌（无数据时为 None）。

    ``order="size"`` 按成分股只数降序（历史默认）；``order="change"`` 按最近
    交易日等权涨幅降序（无数据的排在最后，同涨幅按规模降序）。涨跌聚合来自
    :func:`get_concept_daily_changes`，按交易日缓存 24 小时，因此两种排序都不产生
    逐概念的上游调用；前端也可以直接用返回值给关联概念、当前概念贴涨幅。
    """
    connection = _industry_connection()
    if query.strip():
        rows = connection.execute(
            "SELECT name, stock_count FROM stock_concepts "
            "WHERE name LIKE ? ORDER BY stock_count DESC, name ASC LIMIT ?",
            (f"%{query.strip()}%", limit),
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT name, stock_count FROM stock_concepts ORDER BY stock_count DESC, name ASC LIMIT ?",
            (limit,),
        ).fetchall()

    changes = get_concept_daily_changes()
    summaries: list[ConceptSummary] = []
    for row in rows:
        name = str(row[0])
        change = changes.get(name)
        summaries.append(
            ConceptSummary(
                name=name,
                stock_count=int(row[1]),
                change_pct=change.change_pct if change else None,
                change_date=change.date if change else None,
                up_count=change.up_count if change else None,
                down_count=change.down_count if change else None,
                limit_up_count=change.limit_up_count if change else None,
                sample_count=change.sample_count if change else None,
            )
        )

    if order == "change":
        summaries.sort(
            key=lambda item: (
                -(item.change_pct if item.change_pct is not None else float("-inf")),
                -item.stock_count,
                item.name,
            )
        )
    return summaries


def get_concept_daily_changes() -> dict[str, ConceptDailyChange]:
    """全部概念的最近交易日等权涨跌聚合，键为概念名。

    口径与合成指数一致：前复权价、等权平均（见 :mod:`app.modules.market_daily.concept_index`），
    但只算最近两个交易日，成本一次到位（全市场 ~5000 只 × 两日复权价 + 概念映射展开），
    结果按 ``concept_changes:{date}`` 缓存 24 小时。供概念列表排序与标签展示使用，
    不做逐概念的上游调用。
    """
    market_daily = _market_daily_connection()
    date_rows = market_daily.execute(
        "SELECT DISTINCT trade_date FROM market_daily_bars "
        "WHERE market = 'cn' AND instrument_type = 'stock' "
        "ORDER BY trade_date DESC LIMIT 2"
    ).fetchall()
    if len(date_rows) < 2:
        return {}
    latest = str(date_rows[0]["trade_date"])
    prev = str(date_rows[1]["trade_date"])

    cache_key = f"concept_changes:{latest}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    # 两日的复权价：走 (trade_date DESC, market, instrument_type, code) 索引
    price_rows = market_daily.execute(
        """SELECT b.code AS code, b.trade_date AS trade_date,
                  b.close * f.qfq_multiplier + f.qfq_offset AS px
             FROM market_daily_bars b
             JOIN market_daily_adjustment_factors f
               ON f.market = b.market AND f.code = b.code AND f.trade_date = b.trade_date
            WHERE b.market = 'cn'
              AND b.instrument_type = 'stock'
              AND b.trade_date IN (?, ?)
              AND b.close > 0""",
        (prev, latest),
    ).fetchall()
    prices: dict[str, dict[str, float]] = {}
    for row in price_rows:
        prices.setdefault(str(row["code"]), {})[str(row["trade_date"])] = float(row["px"])

    # 个股一日收益（复权，与合成指数的日收益率同口径）
    returns: dict[str, float] = {}
    for code, by_date in prices.items():
        prev_px = by_date.get(prev)
        latest_px = by_date.get(latest)
        if prev_px is None or latest_px is None or prev_px <= 0:
            continue
        returns[code] = (latest_px / prev_px - 1.0) * 100.0
    if not returns:
        return {}

    # 概念映射展开聚合：一只股票平均带 20~40 个概念，Python 侧累加 ~12 万次，可忽略
    industry = _industry_connection()
    mapping_rows = industry.execute(
        "SELECT stock_code, concepts_json FROM stock_concept_mappings"
    ).fetchall()
    sums: dict[str, list[float]] = {}
    for row in mapping_rows:
        code = _split_code(str(row["stock_code"]))
        change = returns.get(code)
        if change is None:
            continue
        for name in _parse_concepts(row["concepts_json"]):
            bucket = sums.get(name)
            if bucket is None:
                bucket = sums[name] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            bucket[0] += change
            bucket[1] += 1.0 if change > 0 else 0.0
            bucket[2] += 1.0 if change < 0 else 0.0
            bucket[3] += 1.0 if change >= 9.8 else 0.0
            bucket[5] += 1.0

    result = {
        name: ConceptDailyChange(
            date=latest,
            change_pct=round(bucket[0] / bucket[5], 4),
            up_count=int(bucket[1]),
            down_count=int(bucket[2]),
            limit_up_count=int(bucket[3]),
            sample_count=int(bucket[5]),
        )
        for name, bucket in sums.items()
    }
    cache.set(cache_key, result, ttl=CONCEPT_LINKAGE.ttl_seconds)
    return result


def _concept_constituent_rows(concept: str) -> list[sqlite3.Row]:
    connection = _industry_connection()
    return connection.execute(
        """SELECT stock_code, stock_name, concepts_json
             FROM stock_concept_mappings
            WHERE EXISTS (
                    SELECT 1 FROM json_each(
                        CASE WHEN json_valid(concepts_json) THEN concepts_json ELSE '[]' END
                    ) WHERE json_each.value = ?
                  )
            ORDER BY stock_code""",
        (concept,),
    ).fetchall()


def _split_code(raw: str) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return normalize_code(text.split(".")[0]).raw
    except ValueError:
        return None


def _parse_concepts(value: object) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]


def list_constituents(concept: str) -> tuple[list[ConceptConstituent], int]:
    """返回概念成分股（不含行情）与总只数。"""
    rows = _concept_constituent_rows(concept)
    if not rows:
        return [], 0
    constituents: list[ConceptConstituent] = []
    for row in rows:
        code = _split_code(str(row["stock_code"]))
        if code is None:
            continue
        constituents.append(
            ConceptConstituent(
                code=code,
                name=str(row["stock_name"] or ""),
                concepts=_parse_concepts(row["concepts_json"]),
            )
        )
    return constituents, len(constituents)


def _all_concept_sizes() -> dict[str, int]:
    """全部概念的成分股只数，按天缓存。用于把"具体题材"排在"普适属性"前面。"""
    cache_key = "concept_sizes:all"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    connection = _industry_connection()
    rows = connection.execute("SELECT name, stock_count FROM stock_concepts").fetchall()
    sizes = {str(row["name"]): int(row["stock_count"]) for row in rows}
    cache.set(cache_key, sizes, ttl=CONCEPT_LINKAGE.ttl_seconds)
    return sizes


def _concept_sizes(names: list[str]) -> dict[str, int]:
    if not names:
        return {}
    connection = _industry_connection()
    placeholders = ",".join("?" * len(names))
    rows = connection.execute(
        f"SELECT name, stock_count FROM stock_concepts WHERE name IN ({placeholders})",
        names,
    ).fetchall()
    return {str(row["name"]): int(row["stock_count"]) for row in rows}


def _confirmed_local_closes(codes: list[str]) -> dict[str, dict]:
    """读取**当日已确认**的本地收盘数据，用于实时行情缺失时兜底。

    仅当本地已有当日 confirmed 收盘时才返回数据，因此绝不会把昨日收盘价
    当作今日价展示：非交易日、盘中未归档、或数据仍为 provisional 时都查不到行。
    涨跌幅由 close 与前一个交易日 close 计算（库内 change_pct 多为 NULL）。
    """
    today = datetime.now(SHANGHAI_TIMEZONE).date().isoformat()
    rows = market_daily_bar_service.repository.list_confirmed_closes(codes, today)
    result: dict[str, dict] = {}
    for code, payload in rows.items():
        close = payload.get("close")
        pre_close = payload.get("pre_close")
        if close is None:
            continue
        change_pct = None
        if pre_close:
            change_pct = (close / pre_close - 1) * 100
        raw_amount = payload.get("amount")
        result[code] = {
            "close": close,
            "change_pct": change_pct,
            "amount": int(raw_amount) if raw_amount is not None else None,
            "source": f"market_daily_close:{today}",
        }
    return result


#: 每只成分股回给前端的"其他概念"标签数（不含当前概念）。
#: 上游 iwencai 每只股票带 20~40 个标签，全量回传会让响应体多出几百 KB；
#: 这里按"具体程度"取最细的几个，足够用户判断这只股票还属于哪些题材。
CONSTITUENT_TAG_LIMIT = 3


def _pick_constituent_tags(
    concept: str,
    concepts: list[str],
    *,
    concept_size: int,
    sizes: dict[str, int],
) -> list[str]:
    """挑出最具体的 N 个其他概念标签。

    ``concept_size`` 是当前概念的成分股只数：融资融券、深股通这类普适属性
    （3861/1879 只）对任何题材都是噪音，因此只保留规模不超过当前概念 2 倍的
    标签，再按规模升序取最细的几个——「人形机器人」优先于「预盈预增」。
    """
    size_limit = max(concept_size, 1) * 2
    candidates = [
        name
        for name in concepts
        if name != concept and sizes.get(name, 0) <= size_limit
    ]
    candidates.sort(key=lambda name: (sizes.get(name, 0), name))
    return candidates[:CONSTITUENT_TAG_LIMIT]


def _related_concepts(concept: str, constituents: list[ConceptConstituent]) -> list[RelatedConcept]:
    """统计与当前概念重叠最多的其他概念。

    成分股查询时 ``concepts_json`` 已经读进内存，直接在 Python 侧聚合，
    不需要额外 SQL。每只股票平均带 20~40 个概念标签，全量回给前端会让
    响应体多出几百 KB，而用户真正需要的是"这个概念和谁重叠"。
    """
    if not constituents:
        return []
    counter: Counter[str] = Counter()
    for item in constituents:
        counter.update(name for name in item.concepts if name != concept)
    if not counter:
        return []

    total = len(constituents)
    size_limit = total * RELATED_MAX_SIZE_RATIO
    # 先多取一些候选，再按规模过滤，避免过滤后不足 RELATED_CONCEPT_LIMIT 条
    sizes = _concept_sizes([name for name, _ in counter.most_common(RELATED_CONCEPT_LIMIT * 4)])
    ranked: list[RelatedConcept] = []
    for name, count in counter.most_common(RELATED_CONCEPT_LIMIT * 4):
        if sizes.get(name, total + 1) > size_limit:
            continue
        ranked.append(RelatedConcept(name=name, overlap=count, ratio=round(count / total, 4)))
        if len(ranked) >= RELATED_CONCEPT_LIMIT:
            break
    return ranked


async def get_concept_constituents(concept: str, quote_codes: list[str] | None = None) -> dict:
    """概念成分股 + 实时行情 + 重叠最多的相关概念。

    行情缺失只降级为 ``None``，不影响成分身份与相关概念统计。

    ``quote_codes`` 用于按需加载：前端虚拟滚动只请求当前可见区的代码，
    避免为一个概念同步拉取全部（融资融券这类可达 1500 只）实时行情——
    上游按 80 条一批串行处理（TDX 客户端非线程安全，统一锁内串行），
    全量请求在上游故障时会拖到数十秒。缺省为 None 表示仍然全量拉取。
    """
    constituents, total = await asyncio.to_thread(list_constituents, concept)
    if not constituents:
        raise ResourceNotFoundError(f"未找到概念「{concept}」的成分股", code="concept.not_found")

    quotes: dict[str, dict] = {}
    quoted_at: str | None = None
    quote_source: str | None = None
    quote_set = None

    # 只对成分股内的代码取行情，避免请求方传入无关代码放大上游压力
    known_codes = {item.code for item in constituents}
    if quote_codes is None:
        codes = [item.code for item in constituents]
    else:
        codes = [code for code in dict.fromkeys(quote_codes) if code in known_codes]
    if not codes:
        # 没有需要取行情的代码，直接走降级路径
        logger.debug("概念成分股无需拉取行情: concept=%s", concept)
    else:
        try:
            quote_set = await asyncio.wait_for(fetch_realtime_quote_set(codes), timeout=QUOTE_FETCH_TIMEOUT_SECONDS)
            quoted_at = quote_set.quoted_at
            quote_source = quote_set.source
            for raw_code, quote in quote_set.quotes.items():
                if isinstance(quote, dict):
                    quotes[raw_code] = quote
        except Exception as error:  # 行情不可用或超时不应让成分股列表整体失败
            logger.warning("概念成分股行情不可用或拉取超时: concept=%s, error=%s", concept, error)

    items: list[dict] = []
    # 实时行情没覆盖到的行，若本地已有**当日已确认**的收盘数据则用它兜底。
    # 只认verification_status='confirmed'：它由 17:00 之后的 recheck 写入，
    # 天然等价于"当日已定稿"，无需再判断时间；16:20~17:00 只有 provisional，
    # 查不到行也就不会拿未定稿数据冒充今日价。
    local_codes = [item.code for item in constituents if item.code not in quotes]
    local_closes: dict[str, dict] = {}
    if local_codes:
        try:
            local_closes = await asyncio.to_thread(_confirmed_local_closes, local_codes)
        except Exception:
            logger.warning("概念成分股本地收盘兜底失败: concept=%s", concept, exc_info=True)

    # 行内"其他概念"标签：规模表按天缓存，挑选规则见 _pick_constituent_tags
    concept_sizes = await asyncio.to_thread(_all_concept_sizes)
    concept_size = concept_sizes.get(concept, total)

    for item in constituents:
        quote = quotes.get(item.code)
        price = change_pct = None
        amount = None
        source = None
        if quote is not None:
            price = safe_float(quote.get("price"))
            change_pct = safe_float(quote.get("change_pct"))
            raw_amount = safe_float(quote.get("amount"))
            amount = int(raw_amount) if raw_amount is not None else None
            source = quote_set.quote_sources.get(item.code) if quote_set is not None else None
        else:
            local = local_closes.get(item.code)
            if local is not None:
                price = local["close"]
                change_pct = local["change_pct"]
                amount = local["amount"]
                source = local["source"]
        items.append(
            {
                "code": item.code,
                "name": item.name,
                "price": price,
                "change_pct": change_pct,
                "amount": amount,
                "quote_source": source,
                "related_concepts": _pick_constituent_tags(
                    concept,
                    item.concepts,
                    concept_size=concept_size,
                    sizes=concept_sizes,
                ),
            }
        )

    related = await asyncio.to_thread(_related_concepts, concept, constituents)
    return {
        "concept": concept,
        "total": total,
        "items": items,
        "related_concepts": [{"name": item.name, "overlap": item.overlap, "ratio": item.ratio} for item in related],
        "quoted_at": quoted_at,
        "quote_source": quote_source,
        "quote_covered": sum(1 for item in items if item["price"] is not None),
    }


async def get_concept_index(concept: str, *, days: int) -> dict:
    """本地合成的等权概念指数。"""
    if days <= 0:
        raise InvalidRequestError("days 必须大于 0")
    days = min(days, MAX_INDEX_DAYS)
    cache_key = f"concept_index:{concept}:{days}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    constituents, total = await asyncio.to_thread(list_constituents, concept)
    if not constituents:
        raise ResourceNotFoundError(f"未找到概念「{concept}」的成分股", code="concept.not_found")

    codes = [item.code for item in constituents]
    used_codes = sample_constituents(codes)
    start_date = (market_today() - timedelta(days=days)).isoformat()
    points = await asyncio.to_thread(load_concept_index, used_codes, start_date)
    payload = {
        "concept": concept,
        "method": "equal_weight_adjusted_close",
        "base": points[0].level if points else None,
        "constituent_total": total,
        "constituent_used": len(used_codes),
        "truncated": len(used_codes) < total,
        "items": [
            {
                "date": point.date,
                "open": round(point.open, 4),
                "high": round(point.high, 4),
                "low": round(point.low, 4),
                "close": round(point.level, 4),
                "change_pct": round(point.avg_ret, 4),
                "amount": point.amount,
                "up_count": point.up_count,
                "down_count": point.down_count,
                "limit_up_count": point.limit_up_count,
                "limit_down_count": point.limit_down_count,
                "sample_count": point.sample_count,
            }
            for point in points
        ],
    }
    cache.set(cache_key, payload, ttl=CONCEPT_LINKAGE.ttl_seconds)
    return payload
