import json
from datetime import date, time
from typing import Any

from app.core.news import parse_news_datetime
from app.modules.daily_review.models import (
    CycleTrend,
    DailyReviewDataSnapshot,
    DailyReviewEventImpact,
    DailyReviewPreviousCheck,
    DailyReviewResult,
    DailyReviewSection,
    DailyReviewSourceStatus,
    DailyReviewWatchItem,
    PolicyNewsSnapshotItem,
)
from app.modules.daily_review.news_policy import classify_policy_news

_EVENT_TYPE_LABELS = {
    "policy": "政策",
    "macro": "宏观",
    "global": "海外",
    "industry": "产业",
    "market": "市场",
}
_DIRECTION_LABELS = {
    "positive": "偏利好",
    "negative": "偏利空",
    "mixed": "影响分化",
    "neutral": "方向待确认",
}
_TIMING_LABELS = {
    "before": "盘前/事前信息",
    "on_date": "复盘日信息",
    "after": "事后验证",
}


def _is_housing_interest_subsidy(title: str, content: str) -> bool:
    text = f"{title} {content}".lower()
    housing = any(keyword in text for keyword in ("购房", "住房贷款", "房贷", "按揭", "首套房", "mortgage"))
    subsidy = any(keyword in text for keyword in ("贴息", "利息补贴", "mortgage subsidy", "mortgage subsidies"))
    return housing and subsidy


def _is_post_close_publication(item) -> bool:
    if item.timing != "on_date":
        return False
    published = parse_news_datetime(
        item.publish_time,
        allow_relative=False,
        allow_time_only=False,
    )
    # 00:00 通常来自只含日期的 URL 归档值，不能据此断言为盘前发布。
    return published is not None and published.time() != time.min and published.time() >= time(15, 0)


def _apply_publication_cutoff(
    item,
    transmission_chain: str,
    confirmation_signals: list[str],
) -> tuple[str, list[str]]:
    if item.timing == "after":
        return (
            f"事后发布，不用于解释复盘日走势；{transmission_chain}",
            ["仅用复盘日后的盘面和数据验证，不反向归因当日行情", *confirmation_signals[:2]],
        )
    if _is_post_close_publication(item):
        return (
            f"复盘日收盘后发布，不用于解释当日收盘；作为下一交易日及后续基本面线索：{transmission_chain}",
            ["下一交易日相关板块竞价、成交额与龙头强弱", *confirmation_signals],
        )
    return transmission_chain, confirmation_signals


def _fallback_impact_details(item) -> tuple[str, str, list[str], list[str]]:
    if _is_housing_interest_subsidy(item.title, item.content):
        transmission_chain, confirmation_signals = _apply_publication_cutoff(
            item,
            (
                "财政贴息降低符合条件家庭的实际房贷成本 → 刚性和改善性购房需求边际释放 → "
                "新房成交与房企回款预期改善 → 地产开发、经纪服务和家居建材估值修复；"
                "银行端同时观察按揭投放增量能否覆盖息差压力"
            ),
            [
                "住建部门高频成交和网签数据连续改善",
                "房地产与家居建材成交额放大且龙头相对强势",
                "新增居民中长期贷款或银行按揭投放回升",
            ],
        )
        return (
            "medium_term",
            transmission_chain,
            confirmation_signals,
            [
                "申请门槛、面积或总价限制使实际覆盖面明显低于预期",
                "政策落地后网签和居民中长期贷款未改善",
                "地产板块仅高开脉冲、成交额和板块扩散不能维持",
            ],
        )
    sectors = item.related_sectors
    sector_text = "、".join(sectors) if sectors else "大盘风险偏好与相关产业链"
    transmission_chain, confirmation_signals = _apply_publication_cutoff(
        item,
        (
            f"{_EVENT_TYPE_LABELS[item.event_type]}事件 → 预期与风险偏好变化 → "
            f"{sector_text}资金关注度变化 → 观察成交额、龙头强弱与板块扩散确认"
        ),
        ["相关板块成交额放大", "中军或龙头相对强势", "板块上涨家数与涨停梯队扩散"],
    )
    return (
        "short_term",
        transmission_chain,
        confirmation_signals,
        ["政策细则弱于预期", "板块高开低走且成交额不能维持", "仅个别概念股脉冲、无行业扩散"],
    )


_SECTOR_CONFIRMATION_ALIASES = {
    "房地产": ("房地产", "地产", "物业", "房屋建设"),
    "银行": ("银行",),
    "券商": ("券商", "证券"),
    "新能源车": ("新能源车", "汽车"),
    "人工智能": ("人工智能", "AI", "算力"),
}


def _sector_matches(sector: str, market_name: str) -> bool:
    aliases = _SECTOR_CONFIRMATION_ALIASES.get(sector, (sector,))
    normalized_name = market_name.lower()
    return any(alias.lower() in normalized_name or normalized_name in alias.lower() for alias in aliases)


def _market_confirmation(snapshot: DailyReviewDataSnapshot, item) -> str:
    if item.timing == "after":
        return "事件发布于复盘日之后，复盘日盘面不能作为该事件的验证证据。"
    if _is_post_close_publication(item):
        return "事件在复盘日收盘后发布，当日板块涨跌不构成该政策的市场反馈，需从下一交易日开始验证。"
    matched: list[tuple[str, float | None, str]] = []
    for group, rows in (("领涨", snapshot.top_sectors), ("领跌", snapshot.bottom_sectors)):
        for row in rows:
            name = str(row.get("name") or "").strip()
            if not name or not any(_sector_matches(sector, name) for sector in item.related_sectors):
                continue
            change = row.get("change_pct")
            matched.append((name, float(change) if isinstance(change, (int, float)) else None, group))
    if not matched:
        return "输入的领涨/领跌板块中未发现与该事件直接对应的方向，尚未获得明确盘面确认。"
    details = "、".join(
        f"{name}{f'{change:+.2f}%' if change is not None else ''}（{group}）"
        for name, change, group in matched[:4]
    )
    has_leader = any(group == "领涨" and (change is None or change > 0) for _, change, group in matched)
    has_laggard = any(group == "领跌" and (change is None or change < 0) for _, change, group in matched)
    if has_leader and not has_laggard:
        verdict = "相关方向已出现初步盘面响应，但仍需成交额与持续性确认"
    elif has_laggard and not has_leader:
        verdict = "相关方向当日表现偏弱，政策逻辑尚未获得盘面确认"
    else:
        verdict = "相关方向表现分化，不能据此认定政策已经被市场定价"
    return f"{details}；{verdict}。"


def _evidence_text(item) -> str:
    direction_text = _DIRECTION_LABELS[item.direction]
    corroboration = (
        f"；交叉来源：{'、'.join(item.corroborating_sources)}"
        if item.corroborating_sources
        else ""
    )
    publication_note = "；盘后发布，不作为当日收盘归因" if _is_post_close_publication(item) else ""
    return (
        f"{item.source or '未知来源'} {item.publish_time or ''}：{item.title}"
        f"（{direction_text}）{publication_note}；原文：{item.url or '无链接'}{corroboration}"
    ).strip()


def build_fallback_event_impacts(snapshot: DailyReviewDataSnapshot) -> list[DailyReviewEventImpact]:
    impacts: list[DailyReviewEventImpact] = []
    for item in snapshot.policy_news[:6]:
        sectors = item.related_sectors
        horizon, transmission_chain, confirmation_signals, invalidation_conditions = _fallback_impact_details(item)
        impacts.append(DailyReviewEventImpact(
            event_title=item.title,
            event_type=item.event_type,
            direction=item.direction,
            timing=item.timing,
            horizon=horizon,
            affected_sectors=sectors,
            transmission_chain=transmission_chain,
            evidence=_evidence_text(item),
            market_confirmation=_market_confirmation(snapshot, item),
            confirmation_signals=confirmation_signals,
            invalidation_conditions=invalidation_conditions,
        ))
    return impacts


def build_fallback_news_policy_section(snapshot: DailyReviewDataSnapshot) -> DailyReviewSection:
    if not snapshot.policy_news:
        return DailyReviewSection(
            title="新闻政策与影响传导",
            summary="未获取到与目标复盘时点匹配且可核验的政策、宏观或产业事件。",
            bullets=["不要用当前新闻回填历史复盘；需补齐目标日期附近的政策与新闻源。"],
        )
    bullets = []
    for item in snapshot.policy_news[:8]:
        sectors = "、".join(item.related_sectors) or "市场整体"
        corroboration = f"；交叉来源：{'、'.join(item.corroborating_sources)}" if item.corroborating_sources else ""
        bullets.append(
            f"[{_EVENT_TYPE_LABELS[item.event_type]}｜{_DIRECTION_LABELS[item.direction]}｜{_TIMING_LABELS[item.timing]}] {item.title}；"
            f"影响方向：{sectors}；主来源：{item.source or '-'} {item.publish_time or ''}{corroboration}".strip()
        )
    return DailyReviewSection(
        title="新闻政策与影响传导",
        summary="区分事实、市场解读与盘面验证；新闻本身不直接等同于可交易结论。",
        bullets=bullets,
    )


def _normalized_event_title(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _matches_event_title(candidate: str, source: str) -> bool:
    normalized_candidate = _normalized_event_title(candidate)
    normalized_source = _normalized_event_title(source)
    if min(len(normalized_candidate), len(normalized_source)) < 6:
        return normalized_candidate == normalized_source
    return normalized_candidate in normalized_source or normalized_source in normalized_candidate


def _snapshot_stock_code_map(snapshot: DailyReviewDataSnapshot) -> dict[str, str]:
    """快照中出现过的个股名称 → 代码，用于校验并补全次日观察锚点。"""
    mapping: dict[str, str] = {}
    candidates: list[dict[str, Any]] = []
    for stock in (snapshot.limit_up_ladder or {}).get("stocks") or []:
        candidates.append(stock)
    for stock in (snapshot.market_statistics or {}).get("limit_up_stocks") or []:
        if isinstance(stock, dict):
            candidates.append(stock)
    candidates.extend(stock for stock in (*snapshot.hot_stocks, *snapshot.dragon_tiger) if isinstance(stock, dict))
    for stock in candidates:
        name = str(stock.get("name") or "").strip()
        code = str(stock.get("code") or "").strip()
        if not name:
            continue
        if name not in mapping or (code and not mapping[name]):
            mapping[name] = code
    return mapping


def _snapshot_stock_names(snapshot: DailyReviewDataSnapshot) -> set[str]:
    """快照中出现过的个股名称集合，用于校验 LLM 是否虚构观察标的。"""
    return set(_snapshot_stock_code_map(snapshot))


def limit_break_rate(snapshot: DailyReviewDataSnapshot) -> float | None:
    """炸板率 = 炸板家数 /（涨停家数 + 炸板家数）；数据缺失时返回 None。"""
    ladder_stocks = (snapshot.limit_up_ladder or {}).get("stocks") or []
    if not ladder_stocks or not snapshot.limit_break_pool:
        return None
    break_count = len((snapshot.limit_break_pool or {}).get("items") or [])
    attempted = len(ladder_stocks) + break_count
    return break_count / attempted if attempted else None


def build_fallback_watchlist(snapshot: DailyReviewDataSnapshot) -> list[DailyReviewWatchItem]:
    """用真实天梯数据给出次日观察锚点（主要在 LLM 未给出或名称不可核验时使用）。"""
    stocks = (snapshot.limit_up_ladder or {}).get("stocks") or []
    if not stocks:
        return []
    by_board = group_limit_up_by_board(stocks)
    max_board = max(by_board)
    space = by_board[max_board][0]
    name = str(space.get("name") or "").strip()
    if not name:
        return []
    return [
        DailyReviewWatchItem(
            name=name,
            code=str(space.get("code") or "").strip(),
            role="连板最高板",
            reason=f"当日空间板（{max_board} 板），代表短线情绪高度与承接力度",
            trigger="次日竞价及开盘半小时能否维持强势，断板或大幅低开视为情绪转弱信号",
        )
    ]


def ground_watchlist(
    snapshot: DailyReviewDataSnapshot,
    items: list[DailyReviewWatchItem],
) -> list[DailyReviewWatchItem]:
    """只保留快照中真实出现过的个股，并用快照代码补全，避免复盘虚构观察标的。"""
    mapping = _snapshot_stock_code_map(snapshot)
    grounded = [
        item.model_copy(update={"code": mapping[name] or item.code.strip()})
        for item in items
        if (name := item.name.strip()) in mapping
    ]
    return grounded[:3] or build_fallback_watchlist(snapshot)


def ground_event_impacts(
    snapshot: DailyReviewDataSnapshot,
    impacts: list[DailyReviewEventImpact],
) -> list[DailyReviewEventImpact]:
    """只保留能回溯到真实新闻标题的 LLM 事件，并强制覆盖来源证据。"""
    grounded: list[DailyReviewEventImpact] = []
    used_titles: set[str] = set()
    for impact in impacts:
        source = next(
            (
                item
                for item in snapshot.policy_news
                if item.title not in used_titles and _matches_event_title(impact.event_title, item.title)
            ),
            None,
        )
        if source is None:
            continue
        used_titles.add(source.title)
        transmission_chain, confirmation_signals = _apply_publication_cutoff(
            source,
            impact.transmission_chain,
            impact.confirmation_signals,
        )
        grounded.append(impact.model_copy(update={
            "event_title": source.title,
            "event_type": source.event_type,
            "direction": source.direction,
            "timing": source.timing,
            "affected_sectors": impact.affected_sectors or source.related_sectors,
            "transmission_chain": transmission_chain,
            "market_confirmation": _market_confirmation(snapshot, source),
            "confirmation_signals": confirmation_signals,
            "evidence": (
                f"{source.source or '未知来源'} {source.publish_time or ''}：{source.title}"
                f"（{source.url or '无链接'}）"
                + (
                    f"；交叉来源：{'、'.join(source.corroborating_sources)}"
                    if source.corroborating_sources
                    else ""
                )
            ).strip(),
        }))
    return grounded or build_fallback_event_impacts(snapshot)


def ground_news_policy_section(
    snapshot: DailyReviewDataSnapshot,
    section: DailyReviewSection,
) -> DailyReviewSection:
    """当模型章节未引用任何真实事件时，退回可核验的确定性摘要。"""
    if not snapshot.policy_news:
        return build_fallback_news_policy_section(snapshot)
    content = " ".join([section.summary, *section.bullets])
    if any(
        _matches_event_title(content, item.title)
        or _normalized_event_title(item.title)[:8] in _normalized_event_title(content)
        for item in snapshot.policy_news
    ):
        return section
    return build_fallback_news_policy_section(snapshot)


def _index_move_counts(snapshot: DailyReviewDataSnapshot) -> tuple[int, int]:
    rising_count = 0
    weak_count = 0
    for item in snapshot.indices:
        change_pct = item.get("change_pct")
        if not isinstance(change_pct, (int, float)):
            continue
        if change_pct > 0:
            rising_count += 1
        elif change_pct < 0:
            weak_count += 1
    return rising_count, weak_count


def _format_limit_stock(stock: dict) -> str:
    name = str(stock.get("name") or stock.get("n") or stock.get("code") or stock.get("c") or "").strip()
    board = stock.get("board_count") or stock.get("lbc")
    sector = str(stock.get("sector_name") or stock.get("hybk") or "").strip()
    if not name:
        return ""
    tag = f"{board}板" if board and int(board) > 1 else "首板"
    extra = f"[{sector}]" if sector else ""
    return f"{name}({tag}{extra})"


def _format_limit_down_stock(stock: dict) -> str:
    name = str(stock.get("name") or stock.get("n") or stock.get("code") or stock.get("c") or "").strip()
    sector = str(stock.get("sector_name") or stock.get("hybk") or "").strip()
    if not name:
        return ""
    extra = f"[{sector}]" if sector else ""
    return f"{name}{extra}"


def _format_distribution(rows: list[dict]) -> str:
    if not rows:
        return ""
    parts = []
    for item in rows:
        label = str(item.get("label", "")).strip()
        count = item.get("count", 0)
        if count and count > 0:
            parts.append(f"{label}%: {count}家")
    return "，".join(parts)


def group_limit_up_by_board(stocks: list[dict]) -> dict[int, list[dict]]:
    """按连板高度分组天梯个股；board_count 缺失或为 0 时视作首板。"""
    by_board: dict[int, list[dict]] = {}
    for stock in stocks:
        board = int(stock.get("board_count") or 1)
        by_board.setdefault(board, []).append(stock)
    return by_board


def _format_limit_up_ladder(ladder: dict[str, Any]) -> str:
    if not ladder:
        return "暂无连板天梯数据"
    stocks = ladder.get("stocks") or []
    sectors = ladder.get("sectors") or []
    if not stocks:
        return "今日无涨停梯队个股"

    by_board = group_limit_up_by_board(stocks)

    max_board = max(by_board) if by_board else 0
    lines = [f"全市场涨停：{len(stocks)}家，连板最高高度（空间板）：{max_board}板"]

    for board in sorted(by_board.keys(), reverse=True):
        stk_list = by_board[board]
        reps = [
            f"{s.get('name')}({s.get('sector_name', '')})"
            for s in stk_list[:8]
            if s.get("name")
        ]
        if len(stk_list) > 8:
            reps.append(f"等共{len(stk_list)}家")
        tag = f"【{board}连板】({len(stk_list)}家)" if board > 1 else f"【首板】({len(stk_list)}家)"
        lines.append(f"- {tag}：{'、'.join(reps)}")

    if sectors:
        top_sec = sorted(sectors, key=lambda x: int(x.get("stock_count") or 0), reverse=True)[:5]
        sec_strs = [
            f"{s.get('sector_name')}({s.get('stock_count')}家涨停)"
            for s in top_sec
            if s.get("sector_name")
        ]
        if sec_strs:
            lines.append(f"- 【最强主线涨停分布】：{' ｜ '.join(sec_strs)}")

    return "\n".join(lines)


def _format_northbound(funds: dict[str, Any]) -> str:
    if not funds:
        return "暂无北向资金数据（可能非交易日或未披露）"
    north = funds.get("north_money")
    if north is None:
        return "暂无北向资金净流入数据"
    sign = "+" if north > 0 else ""
    return f"北向资金净买入：{sign}{north:.2f} 亿元"


def _quant_anchors(snapshot: DailyReviewDataSnapshot) -> str:
    """用 Python 预先算好量化锚点，模型只做解读、不做算术。

    复盘深度依赖「梯队结构、炸板率、量能倍数、涨跌比、资金背离」这类可计算指标；
    让模型自己算会引入幻觉，因此统一在代码里算，并在数据缺失时显式声明不可得。
    """
    lines: list[str] = [
        "以下锚点均由系统预计算，结论必须直接引用这些数字，禁止自行重算或估计。"
    ]

    # 1) 连板梯队结构
    ladder = snapshot.limit_up_ladder or {}
    ladder_stocks = ladder.get("stocks") or []
    by_board = group_limit_up_by_board(ladder_stocks) if ladder_stocks else {}
    max_board = max(by_board) if by_board else 0
    if ladder_stocks:
        multi_board = sum(len(items) for board, items in by_board.items() if board >= 2)
        one_word = sum(1 for stock in ladder_stocks if stock.get("one_word"))
        space_names = [str(s.get("name")) for s in by_board[max_board] if s.get("name")]
        distribution = "、".join(
            f"{board}板 {len(by_board[board])} 家" for board in sorted(by_board, reverse=True)
        )
        gaps = [board for board in range(2, max_board) if board not in by_board]
        ladder_bits = [
            f"涨停 {len(ladder_stocks)} 家（首板 {len(by_board.get(1, []))} 家、二板及以上 {multi_board} 家）",
            f"空间板 {max_board} 板（{'、'.join(space_names[:3])}）",
            f"一字板 {one_word} 家",
            f"板位分布：{distribution}",
        ]
        if gaps:
            ladder_bits.append(f"梯队断层：{'、'.join(f'{board}板' for board in gaps)} 无个股")
        else:
            ladder_bits.append("梯队无断层")
        lines.append("- 连板梯队：" + "；".join(ladder_bits))
    else:
        lines.append("- 连板梯队：天梯数据缺失，禁止推断涨停梯队结构")

    # 2) 涨停主线集中度
    ladder_sectors = ladder.get("sectors") or []
    if ladder_stocks and ladder_sectors:
        ranked = sorted(ladder_sectors, key=lambda item: int(item.get("stock_count") or 0), reverse=True)[:3]
        top3_count = sum(int(item.get("stock_count") or 0) for item in ranked)
        detail = "、".join(
            f"{item.get('sector_name')} {item.get('stock_count')} 家"
            for item in ranked
            if item.get("sector_name")
        )
        ratio = top3_count / len(ladder_stocks)
        lines.append(f"- 涨停主线集中度：Top3 板块 {top3_count} 家，占全市场涨停 {ratio:.0%}（{detail}）")

    # 3) 封板质量：炸板率
    break_pool = snapshot.limit_break_pool or {}
    break_items = break_pool.get("items") or []
    if break_pool and ladder_stocks:
        attempted = len(ladder_stocks) + len(break_items)
        rate = limit_break_rate(snapshot) or 0.0
        lines.append(
            f"- 封板质量：炸板 {len(break_items)} 家，炸板率 {rate:.1%}"
            f"（炸板 {len(break_items)} / 触及涨停 {attempted}）"
        )
    else:
        lines.append("- 封板质量：炸板池数据缺失，炸板率不可得，严禁估算或引用其他日期的炸板率")

    # 4) 两市量能
    volume = snapshot.market_volume or {}
    amount = volume.get("amount")
    if isinstance(amount, (int, float)) and amount > 0:
        volume_bits = [f"成交额 {amount / 100000000.0:.0f} 亿"]
        previous = volume.get("amount_before_one_day")
        if isinstance(previous, (int, float)) and previous > 0:
            delta = amount - previous
            volume_bits.append(f"较前一交易日 {'+' if delta >= 0 else '-'}{abs(delta) / previous:.1%}")
        average_20 = volume.get("amount_average_20_day")
        if isinstance(average_20, (int, float)) and average_20 > 0:
            volume_bits.append(f"为 20 日均值 {amount / average_20:.2f} 倍")
        average_60 = volume.get("amount_average_60_day")
        if isinstance(average_60, (int, float)) and average_60 > 0:
            volume_bits.append(f"为 60 日均值 {amount / average_60:.2f} 倍")
        lines.append("- 两市量能：" + "；".join(volume_bits))
    else:
        lines.append("- 两市量能：成交额数据缺失，禁止推断放量或缩量")

    # 5) 涨跌结构
    statistics = snapshot.market_statistics or {}
    up_count = statistics.get("up_count") or 0
    down_count = statistics.get("down_count") or 0
    if up_count or down_count:
        breadth_bits = [f"涨跌家数 {up_count}:{down_count}"]
        if down_count:
            breadth_bits.append(f"涨跌比 {up_count / down_count:.2f}")
        limit_up_count = statistics.get("limit_up_count") or 0
        limit_down_count = statistics.get("limit_down_count") or 0
        breadth_bits.append(f"涨停 {limit_up_count} 家 / 跌停 {limit_down_count} 家")
        distribution = _format_distribution(statistics.get("stock_pct_distribution") or [])
        if distribution:
            breadth_bits.append(f"涨幅分布 {distribution}")
        lines.append("- 涨跌结构：" + "；".join(breadth_bits))
    else:
        lines.append("- 涨跌结构：涨跌家数数据缺失")

    # 6) 指数K线结构与量价位置
    index_items = [item for item in snapshot.indices if isinstance(item.get("change_pct"), (int, float))]
    if index_items:
        index_bits = []
        for item in index_items[:4]:
            change_pct = float(item.get("change_pct") or 0)
            high = item.get("high")
            low = item.get("low")
            price = item.get("price")
            detail = f"{item.get('name')} {'+' if change_pct >= 0 else ''}{change_pct:.2f}%"
            amplitude = item.get("amplitude")
            if isinstance(amplitude, (int, float)):
                detail += f"（振幅 {float(amplitude):.2f}%"
                if isinstance(high, (int, float)) and isinstance(low, (int, float)) and isinstance(price, (int, float)) and high > low:
                    detail += f"，收盘位于当日振幅 {(price - low) / (high - low):.0%}）"
                else:
                    detail += "）"
            index_bits.append(detail)
        lines.append("- 指数表现：" + "；".join(index_bits))
        rising, weak = _index_move_counts(snapshot)
        lines.append(f"- 指数方向：{rising} 涨 / {weak} 跌（核心指数）")

    # 7) 资金与宽度背离
    north = (snapshot.northbound_funds or {}).get("north_money")
    index_move = None
    if index_items:
        index_move = sum(float(item.get("change_pct") or 0) for item in index_items) / len(index_items)
    divergence_bits: list[str] = []
    if isinstance(north, (int, float)) and index_move is not None:
        north_direction = "净买入" if north > 0 else "净卖出"
        index_direction = "上涨" if index_move > 0 else "下跌" if index_move < 0 else "持平"
        north_sign = "+" if north > 0 else ""
        conflict = (north > 0) != (index_move > 0) and index_move != 0
        divergence_bits.append(
            f"北向 {north_sign}{north:.2f} 亿（{north_direction}）vs 指数 {index_direction}（均值 {index_move:+.2f}%）"
            + ("，方向背离" if conflict else "")
        )
    elif isinstance(north, (int, float)):
        divergence_bits.append(f"北向 {'+' if north > 0 else ''}{north:.2f} 亿")
    if (up_count or down_count) and index_move is not None and down_count:
        conflict = index_move > 0 and up_count < down_count
        if conflict:
            divergence_bits.append(
                f"指数上涨但下跌家数（{down_count}）多于上涨家数（{up_count}），存在宽度背离"
            )
    if divergence_bits:
        lines.append("- 资金与宽度背离：" + "；".join(divergence_bits))

    return "\n".join(lines)


def _market_summary(snapshot: DailyReviewDataSnapshot, prefix: str) -> str:
    market_statistics = snapshot.market_statistics or {}
    rising_count, weak_count = _index_move_counts(snapshot)
    statistics_status = snapshot.source_status.get("market_statistics")
    if statistics_status is not None and statistics_status.status == "unavailable":
        breadth = "市场宽度数据缺失"
    else:
        up_cnt = market_statistics.get("up_count", 0)
        down_cnt = market_statistics.get("down_count", 0)
        flat_cnt = market_statistics.get("flat_count", 0)
        limit_up_cnt = market_statistics.get("limit_up_count", 0)
        limit_down_cnt = market_statistics.get("limit_down_count", 0)
        breadth = (
            f"全市场上涨 {up_cnt} 家、下跌 {down_cnt} 家、"
            f"平盘 {flat_cnt} 家；涨停 {limit_up_cnt} 家、"
            f"跌停 {limit_down_cnt} 家"
        )
        limit_up_stocks = market_statistics.get("limit_up_stocks") or []
        if limit_up_stocks:
            up_reps = [_format_limit_stock(s) for s in limit_up_stocks[:8]]
            up_reps = [s for s in up_reps if s]
            if up_reps:
                breadth += f"；代表性涨停/连板个股：{', '.join(up_reps)}"
        limit_down_stocks = market_statistics.get("limit_down_stocks") or []
        if limit_down_stocks:
            down_reps = [_format_limit_down_stock(s) for s in limit_down_stocks[:5]]
            down_reps = [s for s in down_reps if s]
            if down_reps:
                breadth += f"；跌停/重挫个股：{', '.join(down_reps)}"
        dist_rows = market_statistics.get("stock_pct_distribution") or []
        if dist_rows:
            dist_text = _format_distribution(dist_rows)
            if dist_text:
                breadth += f"；涨跌幅分布：{dist_text}"

    return (
        f"{prefix} {len(snapshot.indices)} 个核心指数，其中上涨 {rising_count} 个、下跌 {weak_count} 个；"
        f"{breadth}。"
    )


def build_fallback_review(
    date: str,
    snapshot: DailyReviewDataSnapshot,
    generated_at: str,
) -> DailyReviewResult:
    index_bullets = []
    for item in snapshot.indices[:6]:
        name = item.get("name")
        if not name:
            continue
        price = item.get("price", "-")
        chg = item.get("change_pct")
        chg_str = f"{chg:+.2f}%" if isinstance(chg, (int, float)) else f"{chg}%"
        amt = item.get("amount")
        amt_str = f"，成交额 {amt / 1e8:.1f}亿" if isinstance(amt, (int, float)) and amt > 0 else ""
        amp = item.get("amplitude")
        amp_str = f"，振幅 {amp:.2f}%" if isinstance(amp, (int, float)) else ""
        high = item.get("high")
        low = item.get("low")
        open_p = item.get("open")
        range_str = f"（开盘 {open_p} / 最高 {high} / 最低 {low}）" if open_p and high and low else ""
        index_bullets.append(f"{name}：收盘 {price}，涨跌幅 {chg_str}{amp_str}{amt_str} {range_str}".strip())

    vol = snapshot.market_volume
    if vol and vol.get("amount"):
        total_amt = vol.get("amount", 0) / 1e8
        vol_head = f"两市总成交额：{total_amt:.2f} 亿元"
        extra = []
        if vol.get("amount_before_one_day"):
            diff = (vol["amount"] - vol["amount_before_one_day"]) / 1e8
            extra.append(f"较前日 {'+' if diff > 0 else ''}{diff:.2f} 亿")
        if vol.get("amount_average_20_day"):
            extra.append(f"20日均值 {vol['amount_average_20_day'] / 1e8:.2f} 亿")
        if vol.get("amount_average_60_day"):
            extra.append(f"60日均值 {vol['amount_average_60_day'] / 1e8:.2f} 亿")
        if extra:
            index_bullets.insert(0, f"{vol_head}（{'，'.join(extra)}）")
        else:
            index_bullets.insert(0, vol_head)


    market_statistics = snapshot.market_statistics or {}
    breadth_available = snapshot.source_status.get("market_statistics", DailyReviewSourceStatus()).status != "unavailable"

    sector_bullets = []
    if snapshot.top_sectors:
        top_str = "、".join(
            f"{s.get('name', '')}({s.get('change_pct', 0):+.2f}%，领涨:{s.get('leading_stock', '-')})"
            for s in snapshot.top_sectors[:5]
            if s.get("name")
        )
        sector_bullets.append(f"领涨行业：{top_str}")
    if snapshot.bottom_sectors:
        bot_str = "、".join(
            f"{s.get('name', '')}({s.get('change_pct', 0):+.2f}%，领跌:{s.get('leading_stock', '-')})"
            for s in snapshot.bottom_sectors[:5]
            if s.get("name")
        )
        sector_bullets.append(f"领跌行业：{bot_str}")
    if snapshot.hot_concepts:
        con_str = "、".join(
            f"{c.get('name', '')}(热度:{c.get('hot_value', '-')})"
            for c in snapshot.hot_concepts[:6]
            if c.get("name")
        )
        sector_bullets.append(f"热门概念：{con_str}")

    dragon_bullets = []
    for item in snapshot.dragon_tiger[:6]:
        name = item.get("name")
        if not name:
            continue
        net = item.get("net_amount", "-")
        net_str = f"{net / 1e4:.1f}万" if isinstance(net, (int, float)) else f"{net}万"
        reason = item.get("reason", "-")
        chg = item.get("change_pct")
        chg_str = f"，涨跌幅 {chg:+.2f}%" if isinstance(chg, (int, float)) else ""
        dragon_bullets.append(f"{name}：净买入 {net_str}{chg_str}，上榜原因：{reason}")

    if snapshot.limit_up_ladder and snapshot.limit_up_ladder.get("stocks"):
        ladder_stocks = snapshot.limit_up_ladder.get("stocks") or []
        by_b = group_limit_up_by_board(ladder_stocks)
        max_b = max(by_b) if by_b else 0
        top_s = by_b.get(max_b, [])
        top_names = "、".join(s.get("name") for s in top_s[:3] if s.get("name"))
        dragon_bullets.insert(0, f"短线连板空间板：{max_b}板（{top_names}），连板家数合计 {sum(len(v) for k, v in by_b.items() if k > 1)} 家")

    if snapshot.northbound_funds and snapshot.northbound_funds.get("north_money") is not None:
        north = snapshot.northbound_funds.get("north_money")
        sign = "+" if north > 0 else ""
        dragon_bullets.append(f"北向资金：当日净流入 {sign}{north:.2f} 亿元")

    event_impacts = build_fallback_event_impacts(snapshot)
    return DailyReviewResult(
        date=date,
        title=f"{date} 每日复盘",
        generated_at=generated_at,
        market_summary=_market_summary(snapshot, "当日共整理"),
        index_review=DailyReviewSection(title="指数与量价格局", summary="主要指数涨跌、振幅与量价概览如下。", bullets=index_bullets),
        hotspot_review=DailyReviewSection(
            title="板块轮动与题材生命周期",
            summary="优先根据板块涨跌榜识别强势主线与杀跌板块，再辅以热点概念热度。",
            bullets=sector_bullets or ["暂无板块轮动明细数据。"],
        ),
        dragon_tiger_review=DailyReviewSection(
            title="情绪周期与资金微观动向",
            summary="选取当日活跃席位与异动个股，观察主力资金流动与短线情绪偏好。",
            bullets=dragon_bullets or ["暂无龙虎榜活跃个股数据。"],
        ),
        news_policy_review=build_fallback_news_policy_section(snapshot),
        event_impacts=event_impacts,
        risk_alerts=[
            "市场宽度数据缺失，无法判断真实赚钱效应与退潮压力。"
            if not breadth_available
            else
            "若跌停家数抬升且下跌家数明显多于上涨家数，需警惕情绪退潮与高位分歧杀跌。"
            if market_statistics.get("down_count", 0) > market_statistics.get("up_count", 0)
            else "若强势板块集中且龙虎榜净买入不持续，需防范次日冲高回落与分时脉冲陷阱。"
        ],
        opportunities=[
            "核心数据不足，暂不生成方向性机会判断。"
            if not breadth_available
            else
            "优先关注指数相对强势背景下，涨幅居前且有中军龙头带动的板块低吸机会。"
            if market_statistics.get("up_count", 0) >= market_statistics.get("down_count", 0)
            else "若指数分化但板块龙头延续，可关注具备防守属性或独立逻辑的高辨识度个股低吸。"
        ],
        strategy_notes=[
            "仓位管理：建议根据当前市场状态保持 3~5 成中性仓位，控制追高敞口。"
            if breadth_available
            else "先补齐市场宽度和成交额数据，再制定具体仓位比例与交易计划。",
            f"盘面定性：全市场涨停 {market_statistics.get('limit_up_count', 0)} 家、跌停 {market_statistics.get('limit_down_count', 0)} 家，关注高低位板块切换与连板高度突破。",
            "推演预案：若次日早盘放量高开，可聚焦领涨主线分歧转一致低吸；若缩量低开弱势震荡，则严控仓位防守观望。",
        ],
        next_day_watchlist=build_fallback_watchlist(snapshot),
        data_snapshot=snapshot,
    )


def _market_volume_summary(snapshot: DailyReviewDataSnapshot) -> str:
    labels = {
        "amount": "成交额",
        "amount_before_one_day": "昨日成交额",
        "amount_average_20_day": "20日成交额均值",
        "amount_average_60_day": "60日成交额均值",
    }
    parts = []
    for key, label in labels.items():
        value = snapshot.market_volume.get(key)
        if value is None:
            continue
        value = value / 100000000.0 if isinstance(value, (int, float)) else value
        value_text = f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
        parts.append(f"{label}: {value_text}亿")
    return " ".join(parts) + (" " if parts else "")



def _macro_summary(snapshot: DailyReviewDataSnapshot) -> str:
    bullets = []
    macro = snapshot.macro_data or {}
    cpi_latest = macro.get("cpi", {}).get("latest")
    if cpi_latest:
        bullets.append(
            f"CPI({cpi_latest.get('TIME', '')}): 同比 {cpi_latest.get('NATIONAL_SAME', '-')}%, "
            f"环比 {cpi_latest.get('NATIONAL_SEQUENTIAL', '-')}%, 累计 {cpi_latest.get('NATIONAL_ACCUMULATE', '-')}%"
        )
    ppi_latest = macro.get("ppi", {}).get("latest")
    if ppi_latest:
        bullets.append(
            f"PPI({ppi_latest.get('TIME', '')}): 当月 {ppi_latest.get('BASE', '-')}, "
            f"同比 {ppi_latest.get('BASE_SAME', '-')}%"
        )
    pmi_latest = macro.get("pmi", {}).get("latest")
    if pmi_latest:
        bullets.append(
            f"PMI({pmi_latest.get('TIME', '')}): 制造业 {pmi_latest.get('MAKE_INDEX', '-')} "
            f"(同比 {pmi_latest.get('MAKE_SAME', '-')}%), "
            f"非制造业 {pmi_latest.get('NMAKE_INDEX', '-')} "
            f"(同比 {pmi_latest.get('NMAKE_SAME', '-')}%)"
        )
    money_latest = macro.get("money_supply", {}).get("latest")
    if money_latest:
        bullets.append(
            f"货币供应({money_latest.get('TIME', '')}): "
            f"M2 {money_latest.get('BASIC_CURRENCY', '-')}亿 (同比 {money_latest.get('BASIC_CURRENCY_SAME', '-')}%), "
            f"M1 {money_latest.get('CURRENCY', '-')}亿 (同比 {money_latest.get('CURRENCY_SAME', '-')}%), "
            f"M0 {money_latest.get('FREE_CASH', '-')}亿 (同比 {money_latest.get('FREE_CASH_SAME', '-')}%)"
        )
    data_text = "\n".join(bullets) if bullets else "暂无最新宏观数据"
    events_text = _macro_event_summary(snapshot)
    return f"{data_text}\n\n{events_text}" if events_text else data_text


def _macro_event_summary(snapshot: DailyReviewDataSnapshot) -> str:
    """AI 宏观事件解读：历史条目给出解读，待解读条目只给原文。"""
    analysis = snapshot.macro_analysis or {}
    events = analysis.get("events") or []
    if not events:
        return ""
    lines: list[str] = []
    summary = str(analysis.get("summary") or "").strip()
    if summary:
        sentiment = str(analysis.get("sentiment") or "中性")
        lines.append(f"AI 宏观综述（{sentiment}）：{summary}")
    pending_count = int(analysis.get("pending_count") or 0)
    if pending_count:
        lines.append(f"（{pending_count} 条最新事件仍在后台解读，已展示原文）")
    for event in events[:12]:
        if not isinstance(event, dict):
            continue
        event_date = str(event.get("date") or "")[:10]
        title = str(event.get("title") or "").strip()
        if not title:
            continue
        if event.get("pending"):
            lines.append(f"- [{event_date}] {title}（待解读）")
            continue
        category = str(event.get("category") or "其他")
        impact = str(event.get("impact") or "中性")
        interpretation = str(event.get("interpretation") or "").strip()
        detail = f" — {interpretation}" if interpretation and interpretation != title else ""
        lines.append(f"- [{event_date}]（{category}/{impact}）{title}{detail}")
    signals = analysis.get("policy_signals") or []
    if signals:
        lines.append(f"政策信号：{'、'.join(str(signal) for signal in signals[:8])}")
    return "\n".join(lines)


def _news_identity(url: str, title: str) -> str:
    """新闻去重键：优先 URL，缺失时退化到标题。"""
    normalized_url = (url or "").strip()
    if normalized_url:
        return normalized_url
    return (title or "").strip()


def _percent(value: float | None, *, digits: int = 2) -> str:
    return f"{value:+.{digits}f}%" if isinstance(value, (int, float)) else "-"


def _ratio(value: float | None) -> str:
    return f"{value:.2f}" if isinstance(value, (int, float)) else "-"


def _previous_review_check_block(check: DailyReviewPreviousCheck) -> str:
    """把上一交易日的自检结果渲染成 Prompt 区块（复盘闭环的事实依据）。"""
    lines = [f"# 上一交易日复盘自检（{check.review_date} → {check.verified_date}）"]
    if check.checked_count:
        rate = f"{check.hit_rate:.0%}" if check.hit_rate is not None else "-"
        lines.append(f"- 观察标的命中：{check.hit_count}/{check.checked_count}（收涨比例 {rate}）")
    else:
        lines.append("- 观察标的命中：暂无可核验行情")
    for item in check.watchlist[:6]:
        if item.missing:
            lines.append(f"  - {item.name}({item.code or '-'})：次日行情缺失")
            continue
        flag = "涨停" if item.limit_up else ("上涨" if item.hit else "下跌")
        lines.append(f"  - {item.name}({item.code or '-'})：{_percent(item.change_pct)}（{flag}）")
    index_parts = [
        f"{item.name} {_percent(item.previous_change_pct)} → {_percent(item.change_pct)}"
        for item in check.indices[:4]
    ]
    if index_parts:
        lines.append(f"- 指数表现：{'；'.join(index_parts)}")
    if check.limit_up_delta is not None:
        lines.append(
            f"- 涨停家数：{check.previous_limit_up_count} → {check.limit_up_count}"
            f"（{check.limit_up_delta:+d}）"
        )
    if check.previous_stage:
        lines.append(f"- 上一交易日情绪阶段：{check.previous_stage}")
    if check.note:
        lines.append(f"- 数据说明：{check.note}")
    lines.append("- 要求：必须逐条说明昨日预判命中或落空的原因，并据此修正今日定位，不得回避。")
    return "\n".join(lines)


def _cycle_trend_block(trend: CycleTrend) -> str:
    """渲染情绪周期历史趋势，让模型知道当前处在周期的哪个位置。"""
    if not trend.points:
        return f"# 情绪周期历史趋势\n- {trend.note or '暂无历史样本。'}"
    lines = [f"# 情绪周期历史趋势（最近 {len(trend.points)} 个交易日，按时间升序）"]
    for point in trend.points[-10:]:
        parts = [point.date, point.stage or "未定位"]
        if point.limit_up_count is not None:
            parts.append(f"涨停{point.limit_up_count}")
        if point.break_rate is not None:
            parts.append(f"炸板{point.break_rate:.1%}")
        if point.up_down_ratio is not None:
            parts.append(f"涨跌比{_ratio(point.up_down_ratio)}")
        parts.append(f"指数{_percent(point.index_change_pct)}")
        parts.append(f"次日{_percent(point.next_index_change_pct)}")
        if point.stage_transition:
            parts.append(point.stage_transition)
        lines.append("- " + "｜".join(parts))
    for stat in trend.stage_stats[:4]:
        up_ratio = f"{stat.next_day_up_ratio:.0%}" if stat.next_day_up_ratio is not None else "-"
        summary = (
            f"- 阶段统计：{stat.stage} 出现 {stat.occurrences} 次，次日指数上涨比例 {up_ratio}，"
            f"平均次日指数 {_percent(stat.avg_next_day_index_change_pct)}"
        )
        if stat.avg_limit_up_delta is not None:
            summary += f"，平均涨停变化 {stat.avg_limit_up_delta:+.1f}"
        lines.append(summary)
    if trend.note:
        lines.append(f"- 数据说明：{trend.note}")
    lines.append("- 要求：结合趋势判断当前阶段是延续还是切换，并给出与历史阶段特征一致的应对。")
    return "\n".join(lines)


def build_prompt(
    date: str,
    snapshot: DailyReviewDataSnapshot,
    prompt_template: str,
    *,
    previous_review_check: DailyReviewPreviousCheck | None = None,
    cycle_trend: CycleTrend | None = None,
) -> str:
    indices_formatted = []
    for item in snapshot.indices[:6]:
        name = item.get("name", "")
        code = item.get("code", "")
        price = item.get("price")
        chg = item.get("change_pct")
        amt = item.get("amount")
        high = item.get("high")
        low = item.get("low")
        open_p = item.get("open")
        pre_close = item.get("pre_close")
        amp = item.get("amplitude")

        chg_str = f"{chg:+.2f}%" if isinstance(chg, (int, float)) else "暂无"
        amt_str = f"{amt / 1e8:.1f}亿元" if isinstance(amt, (int, float)) and amt > 0 else (f"{amt}" if amt else "暂无")
        price_str = f"{price:.2f}" if isinstance(price, (int, float)) else str(price or "暂无")

        kline_parts = []
        if open_p is not None:
            kline_parts.append(f"今开:{open_p}")
        if high is not None:
            kline_parts.append(f"最高:{high}")
        if low is not None:
            kline_parts.append(f"最低:{low}")
        if pre_close is not None:
            kline_parts.append(f"昨收:{pre_close}")
        if amp is not None:
            kline_parts.append(f"振幅:{amp:.2f}%")
        kline_str = f" [{', '.join(kline_parts)}]" if kline_parts else ""
        indices_formatted.append(f"- {name}({code})：收盘 {price_str}，涨跌幅 {chg_str}，成交额 {amt_str}{kline_str}")
    indices_text = "\n".join(indices_formatted) if indices_formatted else json.dumps(snapshot.indices[:6], ensure_ascii=False)

    hot_stock_bullets = [
        f"{item.get('name', '')}({item.get('code', '')})：涨跌幅 {item.get('change_pct', '-') }%，概念 {item.get('concept_tag', '-') }，上榜原因 {item.get('pop_tag', '-') }"
        for item in snapshot.hot_stocks[:8]
        if item.get("name")
    ]
    hot_concept_bullets = [
        f"{item.get('name', '')}：热度 {item.get('hot_value', '-')}, 涨跌幅 {item.get('change_pct', '-') }%"
        for item in snapshot.hot_concepts[:8]
        if item.get("name")
    ]
    top_sector_bullets = [
        f"{item.get('name', '')}：涨跌幅 {item.get('change_pct', '-') }%，领涨股 {item.get('leading_stock', '-') }({item.get('leading_change_pct', '-') }%)"
        for item in snapshot.top_sectors[:8]
        if item.get("name")
    ]
    bottom_sector_bullets = [
        f"{item.get('name', '')}：涨跌幅 {item.get('change_pct', '-') }%，领跌股 {item.get('leading_stock', '-') }({item.get('leading_change_pct', '-') }%)"
        for item in snapshot.bottom_sectors[:8]
        if item.get("name")
    ]
    dragon_bullets = []
    for item in snapshot.dragon_tiger[:10]:
        if not item.get("name"):
            continue
        net = item.get("net_amount", "-")
        net_str = f"{net / 1e4:.1f}万元" if isinstance(net, (int, float)) else f"{net}万"
        reason = item.get("reason", "-")
        chg = item.get("change_pct", "-")
        turnover = item.get("turnover_pct")
        turn_str = f"，换手率 {turnover}%" if turnover is not None else ""
        dragon_bullets.append(f"{item.get('name', '')}({item.get('code', '')})：净买入 {net_str}，涨跌幅 {chg}%{turn_str}，上榜原因：{reason}")

    hot_industry_bullets = [
        f"{item.get('name', '')}：热度 {item.get('hot_value', '-')}, 涨跌幅 {item.get('change_pct', '-') }%"
        for item in snapshot.hot_industries[:8]
        if item.get("name")
    ]
    selected_policy_news = snapshot.policy_news[:16]
    # 政策事件本身就是从市场新闻里挑出来的，同一篇必须在 Prompt 中只出现一次，
    # 否则模型会把一条事件重复计入 event_impacts，并白白多花 token。
    policy_keys = {_news_identity(item.url, item.title) for item in selected_policy_news}
    remaining_news = [
        item
        for item in snapshot.market_news
        if _news_identity(str(item.get("url") or ""), str(item.get("title") or "")) not in policy_keys
    ][:20]
    news_bullets = [
        f"{item.get('publish_time', '-')}｜{item.get('source', '-')}｜{item.get('title', '')}：{str(item.get('content', '-'))[:320]}｜URL:{item.get('url', '-')}"
        for item in remaining_news
        if item.get("title")
    ]
    policy_bullets = [
        (
            f"[{_EVENT_TYPE_LABELS[item.event_type]}｜{_DIRECTION_LABELS[item.direction]}｜{_TIMING_LABELS[item.timing]}] "
            f"{item.publish_time or '-'}｜{item.source or '-'}｜{item.title}｜"
            f"关联方向:{'、'.join(item.related_sectors) or '待识别'}｜URL:{item.url or '-'}｜"
            f"交叉来源:{'、'.join(item.corroborating_sources) or '-'}"
            # 政策事件已从「市场新闻」区块剔除，这里补上正文摘录，保证模型仍有事实依据。
            + (f"｜内容:{item.content[:200]}" if item.content else "")
        )
        for item in selected_policy_news
    ]
    return prompt_template.format(
        date=date,
        indices_placeholder=indices_text,
        quant_anchors_placeholder=_quant_anchors(snapshot),
        previous_review_check_placeholder=(
            _previous_review_check_block(previous_review_check)
            if previous_review_check is not None
            else "# 上一交易日复盘自检\n- 暂无上一交易日复盘可对照（首次生成或历史数据不足），本轮无需对照。"
        ),
        cycle_trend_placeholder=(_cycle_trend_block(cycle_trend) if cycle_trend is not None else "# 情绪周期历史趋势\n- 暂无历史样本。"),
        market_statistics_placeholder=_market_summary(snapshot, "当日整理"),
        limit_up_ladder_placeholder=_format_limit_up_ladder(snapshot.limit_up_ladder),
        northbound_funds_placeholder=_format_northbound(snapshot.northbound_funds),
        dragon_tiger_placeholder="\n".join(dragon_bullets) if dragon_bullets else json.dumps(snapshot.dragon_tiger[:20], ensure_ascii=False),
        hot_stocks_placeholder="\n".join(hot_stock_bullets) if hot_stock_bullets else json.dumps(snapshot.hot_stocks[:20], ensure_ascii=False),
        hot_concepts_placeholder="\n".join(hot_concept_bullets) if hot_concept_bullets else json.dumps(snapshot.hot_concepts[:8], ensure_ascii=False),
        hot_industries_placeholder="\n".join(hot_industry_bullets) if hot_industry_bullets else json.dumps(snapshot.hot_industries[:15], ensure_ascii=False),
        news_placeholder=(
            "\n".join(news_bullets)
            if news_bullets
            else json.dumps(remaining_news, ensure_ascii=False)
            if remaining_news
            else "暂无其他市场新闻（相关新闻已在上方政策/产业事件中单列）"
        ),
        policy_news_placeholder="\n".join(policy_bullets) if policy_bullets else "暂无匹配复盘时点的重点政策事件",
        top_sectors_placeholder="\n".join(top_sector_bullets) if top_sector_bullets else json.dumps(snapshot.top_sectors[:10], ensure_ascii=False),
        bottom_sectors_placeholder="\n".join(bottom_sector_bullets) if bottom_sector_bullets else json.dumps(snapshot.bottom_sectors[:10], ensure_ascii=False),
        market_volume_placeholder=_market_volume_summary(snapshot) or json.dumps(snapshot.market_volume, ensure_ascii=False),
        macro_data_placeholder=_macro_summary(snapshot),
        source_status_placeholder=json.dumps(
            {name: status.model_dump() for name, status in snapshot.source_status.items()},
            ensure_ascii=False,
        ),
    )


def build_snapshot(
    indices,
    hot_stocks,
    hot_concepts,
    hot_industries,
    dragon_tiger,
    market_statistics,
    market_news,
    market_volume,
    macro_data,
    *,
    macro_analysis=None,
    limit_up_ladder=None,
    limit_break_pool=None,
    northbound_funds=None,
    policy_news: list[PolicyNewsSnapshotItem] | None = None,
    requested_date: str = "",
    effective_date: str = "",
    source_status: dict[str, DailyReviewSourceStatus] | None = None,
) -> DailyReviewDataSnapshot:
    market_statistics_data = (
        {}
        if isinstance(market_statistics, Exception) or market_statistics is None
        else market_statistics.model_dump()
    )
    top_sectors = market_statistics_data.get("top_sectors", [])
    bottom_sectors = market_statistics_data.get("bottom_sectors", [])
    market_statistics_data.pop("top_sectors", None)
    market_statistics_data.pop("bottom_sectors", None)
    market_news_items = (
        []
        if isinstance(market_news, Exception) or market_news is None
        else list(market_news)
    )
    try:
        policy_target_date = date.fromisoformat(effective_date) if effective_date else None
    except ValueError:
        policy_target_date = None
    if policy_news is None:
        # 采集阶段已算过一次（collector.DailyReviewCollection.policy_news）；
        # 仅当调用方未提供时才在这里补算，避免对同一份新闻重复分类。
        policy_news = classify_policy_news(market_news_items, target_date=policy_target_date)
    snapshot_data = {
        "requested_date": requested_date,
        "effective_date": effective_date,
        "source_status": source_status or {},
        "indices": []
        if isinstance(indices, Exception) or indices is None
        else [item.model_dump() for item in indices.indices],
        "hot_stocks": [] if isinstance(hot_stocks, Exception) or hot_stocks is None else hot_stocks,
        "hot_concepts": [] if isinstance(hot_concepts, Exception) or hot_concepts is None else hot_concepts,
        "hot_industries": [] if isinstance(hot_industries, Exception) or hot_industries is None else hot_industries,
        "dragon_tiger": [] if isinstance(dragon_tiger, Exception) or dragon_tiger is None else dragon_tiger,
        "market_statistics": market_statistics_data,
        "market_news": [item.model_dump() for item in market_news_items],
        "policy_news": policy_news,
        "top_sectors": top_sectors,
        "bottom_sectors": bottom_sectors,
    }
    if not isinstance(market_volume, Exception) and market_volume is not None:
        snapshot_data["market_volume"] = market_volume.model_dump()
    if not isinstance(macro_data, Exception) and macro_data is not None:
        snapshot_data["macro_data"] = macro_data
    if macro_analysis is not None and not isinstance(macro_analysis, Exception):
        snapshot_data["macro_analysis"] = (
            macro_analysis.model_dump() if hasattr(macro_analysis, "model_dump") else macro_analysis
        )
    if not isinstance(limit_up_ladder, Exception) and limit_up_ladder is not None:
        snapshot_data["limit_up_ladder"] = limit_up_ladder.model_dump() if hasattr(limit_up_ladder, "model_dump") else limit_up_ladder
    if not isinstance(limit_break_pool, Exception) and limit_break_pool is not None:
        snapshot_data["limit_break_pool"] = (
            limit_break_pool.model_dump() if hasattr(limit_break_pool, "model_dump") else limit_break_pool
        )
    if not isinstance(northbound_funds, Exception) and northbound_funds is not None:
        snapshot_data["northbound_funds"] = northbound_funds.model_dump() if hasattr(northbound_funds, "model_dump") else northbound_funds
    return DailyReviewDataSnapshot(**snapshot_data)
