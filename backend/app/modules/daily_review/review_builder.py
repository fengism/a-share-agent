import json

from app.modules.daily_review.models import (
    DailyReviewDataSnapshot,
    DailyReviewResult,
    DailyReviewSection,
    DailyReviewSourceStatus,
)


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
        "amount": "成交量",
        "amount_before_one_day": "昨日成交量",
        "amount_average_60_day": "60日成交量平均值",
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
        f"{item.get('title', '')}：{item.get('content', '-') }"
        for item in snapshot.market_news[:20]
        if item.get("title")
    ]
    return prompt_template.format(
        date=date,
        indices_placeholder=indices_text,
        market_statistics_placeholder=_market_summary(snapshot, "当日整理"),
        dragon_tiger_placeholder="\n".join(dragon_bullets) if dragon_bullets else json.dumps(snapshot.dragon_tiger[:20], ensure_ascii=False),
        hot_stocks_placeholder="\n".join(hot_stock_bullets) if hot_stock_bullets else json.dumps(snapshot.hot_stocks[:20], ensure_ascii=False),
        hot_concepts_placeholder="\n".join(hot_concept_bullets) if hot_concept_bullets else json.dumps(snapshot.hot_concepts[:8], ensure_ascii=False),
        hot_industries_placeholder="\n".join(hot_industry_bullets) if hot_industry_bullets else json.dumps(snapshot.hot_industries[:15], ensure_ascii=False),
        news_placeholder="\n".join(news_bullets) if news_bullets else json.dumps(snapshot.market_news[:20], ensure_ascii=False),
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
        "market_news": []
        if isinstance(market_news, Exception) or market_news is None
        else [item.model_dump() for item in market_news],
        "top_sectors": top_sectors,
        "bottom_sectors": bottom_sectors,
    }
    if not isinstance(market_volume, Exception) and market_volume is not None:
        snapshot_data["market_volume"] = market_volume.model_dump()
    if not isinstance(macro_data, Exception) and macro_data is not None:
        snapshot_data["macro_data"] = macro_data
    return DailyReviewDataSnapshot(**snapshot_data)
