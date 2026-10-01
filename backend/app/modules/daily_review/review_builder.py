import json
from datetime import date, time
from typing import Any

from app.core.news import parse_news_datetime
from app.modules.daily_review.models import (
    DailyReviewDataSnapshot,
    DailyReviewEventImpact,
    DailyReviewResult,
    DailyReviewSection,
    DailyReviewSourceStatus,
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
    return "\n".join(bullets) if bullets else "暂无最新宏观数据"


def build_prompt(
    date: str,
    snapshot: DailyReviewDataSnapshot,
    prompt_template: str,
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
    news_bullets = [
        f"{item.get('publish_time', '-')}｜{item.get('source', '-')}｜{item.get('title', '')}：{str(item.get('content', '-'))[:320]}｜URL:{item.get('url', '-')}"
        for item in snapshot.market_news[:20]
        if item.get("title")
    ]
    policy_bullets = [
        (
            f"[{_EVENT_TYPE_LABELS[item.event_type]}｜{_DIRECTION_LABELS[item.direction]}｜{_TIMING_LABELS[item.timing]}] "
            f"{item.publish_time or '-'}｜{item.source or '-'}｜{item.title}｜"
            f"关联方向:{'、'.join(item.related_sectors) or '待识别'}｜URL:{item.url or '-'}｜"
            f"交叉来源:{'、'.join(item.corroborating_sources) or '-'}"
        )
        for item in snapshot.policy_news[:16]
    ]
    return prompt_template.format(
        date=date,
        indices_placeholder=indices_text,
        market_statistics_placeholder=_market_summary(snapshot, "当日整理"),
        limit_up_ladder_placeholder=_format_limit_up_ladder(snapshot.limit_up_ladder),
        northbound_funds_placeholder=_format_northbound(snapshot.northbound_funds),
        dragon_tiger_placeholder="\n".join(dragon_bullets) if dragon_bullets else json.dumps(snapshot.dragon_tiger[:20], ensure_ascii=False),
        hot_stocks_placeholder="\n".join(hot_stock_bullets) if hot_stock_bullets else json.dumps(snapshot.hot_stocks[:20], ensure_ascii=False),
        hot_concepts_placeholder="\n".join(hot_concept_bullets) if hot_concept_bullets else json.dumps(snapshot.hot_concepts[:8], ensure_ascii=False),
        hot_industries_placeholder="\n".join(hot_industry_bullets) if hot_industry_bullets else json.dumps(snapshot.hot_industries[:15], ensure_ascii=False),
        news_placeholder="\n".join(news_bullets) if news_bullets else json.dumps(snapshot.market_news[:20], ensure_ascii=False),
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
    limit_up_ladder=None,
    northbound_funds=None,
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
    if not isinstance(limit_up_ladder, Exception) and limit_up_ladder is not None:
        snapshot_data["limit_up_ladder"] = limit_up_ladder.model_dump() if hasattr(limit_up_ladder, "model_dump") else limit_up_ladder
    if not isinstance(northbound_funds, Exception) and northbound_funds is not None:
        snapshot_data["northbound_funds"] = northbound_funds.model_dump() if hasattr(northbound_funds, "model_dump") else northbound_funds
    return DailyReviewDataSnapshot(**snapshot_data)
