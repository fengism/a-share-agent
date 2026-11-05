"""国家队响应的聚合计算：把份额 / 收盘历史拼成页面直接消费的结构。

这里只做纯计算，不碰网络与数据库，可以用固定输入直接断言结果；采集、缓存与
落库留在 ``national_team``，这样两边都不会再长成两千行。
"""

from __future__ import annotations

import statistics
from typing import Literal

from app.financial_data.market.quotes.national_team_definitions import (
    DEFAULT_NATIONAL_TEAM_INTRADAY,
    DEFAULT_NATIONAL_TEAM_PORTRAIT,
    DISCLAIMER,
    ETF_POOL,
    INDEX_MIN_COVERAGE,
    INDEX_POOL,
    METHOD,
    NATIONAL_TEAM_MILESTONES,
    YI,
    EtfDefinition,
    IndexDefinition,
)
from app.financial_data.market.quotes.schemas import (
    NationalTeamBacktestHorizon,
    NationalTeamBacktestStatus,
    NationalTeamDailyFlow,
    NationalTeamEtfPoint,
    NationalTeamEtfSeries,
    NationalTeamIndexPoint,
    NationalTeamIndexSeries,
    NationalTeamPortrait,
    NationalTeamResponse,
    NationalTeamShareObservation,
    NationalTeamSummary,
    NationalTeamSupportBacktest,
    NationalTeamSupportHistoryPoint,
    NationalTeamSupportScore,
    NationalTeamSupportZone,
    NationalTeamSupportZoneItem,
)


def _rounded(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _period_change(values: dict[str, float], dates: list[str], sessions: int) -> float | None:
    if len(dates) <= sessions:
        return None
    latest = values.get(dates[-1])
    baseline = values.get(dates[-1 - sessions])
    return None if latest is None or baseline is None else _rounded(latest - baseline)


def _sum_complete(values: list[float | None]) -> float | None:
    if not values or any(value is None for value in values):
        return None
    return _rounded(sum(value for value in values if value is not None))


def _sum_available(values: list[float | None]) -> tuple[float | None, int, int]:
    """对可用值求和，并返回 (合计, 有值数量, 总数)。

    与 :func:`_sum_complete` 的区别：单个缺失不会把整体拖成 ``None``，调用方可
    用数量推导覆盖率，在页面上显示“部分合计 + 覆盖比例”，而不是整块 KPI 变成
    “-”。仅当全部缺失时才返回 ``None``。
    """
    present = [value for value in values if value is not None]
    if not present:
        return None, 0, len(values)
    return _rounded(sum(present)), len(present), len(values)


def _sum_or_none(values: list[float | None]) -> float | None:
    """:func:`_sum_available` 的只要合计版。"""
    return _sum_available(values)[0]


def _index_period_change(points: list[NationalTeamIndexPoint], sessions: int) -> float | None:
    """按指数自身点位求 N 个交易日累计份额变化。

    不能直接用起止总份额相减：成员集合可能随新 ETF 上市变化，相减会把“新增成员”
    误算成资金流入。改为累加逐日份额变化，成员进出不会制造虚假增量。
    """
    if len(points) <= sessions:
        return None
    return _sum_complete([point.shares_change_100m for point in points[-sessions:]])


def _period_flow(points: list[NationalTeamEtfPoint], dates: list[str], sessions: int) -> float | None:
    if len(dates) <= sessions:
        return None
    flows = {point.date: point.estimated_net_flow_100m for point in points}
    # 窗口首日仅作基线；之后每个交易日都必须具备可比份额和收盘价。
    return _sum_complete([flows.get(day) for day in dates[max(1, len(dates) - sessions) :]])


def _build_etf_series(
    definition: EtfDefinition,
    shares: dict[str, float],
    closes: dict[str, float],
    dates: list[str],
    amounts: dict[str, float] | None = None,
) -> NationalTeamEtfSeries:
    points: list[NationalTeamEtfPoint] = []
    previous_dates = dict(zip(dates[1:], dates))
    for point_date in sorted(shares):
        previous_shares = shares.get(previous_dates.get(point_date, ""))
        absolute_shares = float(shares[point_date])
        shares_100m = absolute_shares / YI
        change_100m = None if previous_shares is None else (absolute_shares - previous_shares) / YI
        close = closes.get(point_date)
        change_pct = (
            None if previous_shares in (None, 0) else (absolute_shares - previous_shares) / previous_shares * 100
        )
        flow = None if change_100m is None or close is None else change_100m * close
        amt_100m = (amounts or {}).get(point_date)
        points.append(
            NationalTeamEtfPoint(
                date=point_date,
                shares_100m=round(shares_100m, 4),
                shares_change_100m=_rounded(change_100m),
                shares_change_pct=_rounded(change_pct),
                close=_rounded(close),
                amount_100m=_rounded(amt_100m),
                estimated_net_flow_100m=_rounded(flow),
            )
        )
    share_values = {point.date: point.shares_100m for point in points}
    latest = points[-1] if points else None
    is_current = latest is not None and bool(dates) and latest.date == dates[-1]
    index = INDEX_POOL[definition.index_key]

    latest_amount_100m = latest.amount_100m if latest else None
    volume_ratio: float | None = None
    is_abnormal_volume = False
    if latest and latest.amount_100m is not None and len(points) >= 2:
        prev_amounts = [pt.amount_100m for pt in points[:-1] if pt.amount_100m is not None]
        if prev_amounts:
            recent_5_amounts = prev_amounts[-5:]
            avg_prev = sum(recent_5_amounts) / len(recent_5_amounts)
            if avg_prev > 0:
                volume_ratio = round(latest.amount_100m / avg_prev, 2)
                if volume_ratio >= 1.8 and latest.amount_100m >= 5.0:
                    is_abnormal_volume = True

    return NationalTeamEtfSeries(
        code=definition.code,
        name=definition.name,
        fund_manager=definition.fund_manager,
        exchange=definition.exchange,
        index_key=definition.index_key,
        index_name=index.name,
        category=definition.category,
        latest_date=latest.date if latest else None,
        latest_shares_100m=latest.shares_100m if latest else None,
        latest_change_1d_100m=latest.shares_change_100m if is_current else None,
        change_5d_100m=_period_change(share_values, dates, 5),
        change_20d_100m=_period_change(share_values, dates, 20),
        latest_amount_100m=latest_amount_100m,
        # 表格与 CSV 只需要最新一天的估算净申购，单独给一个标量字段，
        # 就不必为它把整段 points 序列传给前端（占总体积约 65%）。
        latest_estimated_net_flow_100m=latest.estimated_net_flow_100m if latest else None,
        volume_ratio=volume_ratio,
        is_abnormal_volume=is_abnormal_volume,
        points=points,
    )


def _build_index_series(
    definition: IndexDefinition,
    etfs: list[NationalTeamEtfSeries],
    closes: dict[str, float],
    dates: list[str],
) -> NationalTeamIndexSeries:
    member_codes = [item.code for item in ETF_POOL.values() if item.index_key == definition.key]
    member_count = len(member_codes)
    point_maps = {
        item.code: {point.date: point for point in item.points}
        for item in etfs
        if item.index_key == definition.key and item.points
    }
    # 按“当日实际有数据的成员”聚合，而不是取所有成员的日期交集：
    # 一只 ETF 缺一天不应让整条指数当天消失（旧实现会把 1/5/20 日变化全部变成 None）。
    candidate_dates = sorted({day for mapping in point_maps.values() for day in mapping})
    allowed_dates = set(dates)
    points: list[NationalTeamIndexPoint] = []
    cumulative = 0.0
    first_emitted = True
    for point_date in candidate_dates:
        if allowed_dates and point_date not in allowed_dates:
            continue
        day_points = [mapping[point_date] for mapping in point_maps.values() if point_date in mapping]
        if not day_points:
            continue
        covered = len(day_points)
        coverage = covered / member_count if member_count else 0.0
        if member_count > 1 and coverage < INDEX_MIN_COVERAGE:
            continue
        total = sum(point.shares_100m for point in day_points)
        change = _sum_complete([point.shares_change_100m for point in day_points])
        flow = _sum_complete([point.estimated_net_flow_100m for point in day_points])
        if first_emitted:
            cumulative = 0.0
            first_emitted = False
        elif change is not None:
            cumulative += change
        points.append(
            NationalTeamIndexPoint(
                date=point_date,
                total_shares_100m=round(total, 4),
                shares_change_100m=_rounded(change),
                cumulative_change_100m=_rounded(cumulative) or 0,
                index_close=_rounded(closes.get(point_date)),
                estimated_net_flow_100m=_rounded(flow),
                covered_etf_count=covered,
                total_etf_count=member_count,
                coverage_ratio=round(coverage, 4),
            )
        )
    latest = points[-1] if points else None
    is_current = latest is not None and bool(dates) and latest.date == dates[-1]
    return NationalTeamIndexSeries(
        index_key=definition.key,
        index_name=definition.name,
        index_code=definition.index_code,
        category=definition.category,
        etf_codes=member_codes,
        covered_etf_codes=list(point_maps),
        coverage_ratio=latest.coverage_ratio if latest else 0.0,
        latest_date=latest.date if latest else None,
        latest_total_shares_100m=latest.total_shares_100m if latest else None,
        latest_change_1d_100m=latest.shares_change_100m if is_current else None,
        change_5d_100m=_index_period_change(points, 5),
        change_20d_100m=_index_period_change(points, 20),
        estimated_net_flow_1d_100m=latest.estimated_net_flow_100m if is_current else None,
        points=points,
    )


def _score_status(score: float) -> Literal["neutral", "moderate", "active", "strong"]:
    if score >= 80.0:
        return "strong"
    if score >= 60.0:
        return "active"
    if score >= 40.0:
        return "moderate"
    return "neutral"


def _calculate_support_score(
    summary: NationalTeamSummary,
    daily_flows: list[NationalTeamDailyFlow],
    indices: list[NationalTeamIndexSeries],
    *,
    stale: bool = False,
    calendar_degraded: bool = False,
) -> NationalTeamSupportScore:
    """计算国家队托底护盘强度指数（0-100）与置信度（0-1）。

    分数本身是固定阈值的经验模型，**不随数据质量打折**：打折会让同一盘面在不同
    覆盖率下忽高忽低。数据质量单独通过 ``confidence`` 表达，由前端提示用户。
    """
    flow_1d = summary.estimated_net_flow_1d_100m or 0.0
    flow_5d = summary.estimated_net_flow_5d_100m or 0.0

    # 1. 资金托底因子 (0 ~ 40 分)
    if flow_1d >= 80.0 or flow_5d >= 250.0:
        net_flow_factor = 40.0
    elif flow_1d >= 30.0 or flow_5d >= 100.0:
        net_flow_factor = 30.0 + min(10.0, max(0.0, (flow_1d - 30.0) / 5.0))
    elif flow_1d >= 10.0 or flow_5d >= 30.0:
        net_flow_factor = 20.0 + min(10.0, max(0.0, (flow_1d - 10.0) / 2.0))
    elif flow_1d >= 0.0:
        net_flow_factor = 10.0 + min(10.0, max(0.0, flow_1d))
    elif flow_1d >= -20.0:
        net_flow_factor = max(5.0, 10.0 + flow_1d * 0.25)
    else:
        net_flow_factor = 0.0

    # 2. 板块扩散因子 (0 ~ 30 分)
    latest_flow = daily_flows[-1] if daily_flows else None
    cat_flows = latest_flow.flows_by_category if latest_flow else {}
    if cat_flows:
        positive_cats = sum(1 for val in cat_flows.values() if val > 0.05)
        total_cats = max(1, len(cat_flows))
        breadth_factor = round(positive_cats / total_cats * 30.0, 1)
    else:
        # 当天分类资金流还没出来时给中性分，而不是把“缺数据”算成 0 扩散。
        breadth_factor = 15.0

    # 3. 逆势抗跌/托底意图因子 (0 ~ 30 分)
    csi300_series = next((idx for idx in indices if idx.index_key == "csi300"), None)
    latest_pt = csi300_series.points[-1] if csi300_series and csi300_series.points else None
    prev_pt = csi300_series.points[-2] if csi300_series and len(csi300_series.points) >= 2 else None

    if latest_pt and prev_pt and prev_pt.index_close and latest_pt.index_close:
        idx_change_pct = (latest_pt.index_close - prev_pt.index_close) / prev_pt.index_close * 100
        if idx_change_pct < -0.5:
            if flow_1d > 20.0:
                divergence_factor = 30.0
            elif flow_1d > 5.0:
                divergence_factor = 24.0
            elif flow_1d > 0.0:
                divergence_factor = 18.0
            else:
                divergence_factor = 10.0
        elif idx_change_pct > 1.0:
            divergence_factor = 12.0 if flow_1d > 0 else 8.0
        else:
            divergence_factor = 16.0 if flow_1d > 0 else 10.0
    else:
        divergence_factor = 15.0

    total_score = round(min(100.0, max(0.0, net_flow_factor + breadth_factor + divergence_factor)), 1)
    status = _score_status(total_score)

    if status == "strong":
        label = "强力救市"
        description = "核心与成长宽基出现逆势大额承接，全市场托底意愿极其强烈。"
    elif status == "active":
        label = "积极托底"
        description = "主力资金在重点战略宽基上呈现持续净买入，有效构筑下方防线。"
    elif status == "moderate":
        label = "常规调仓"
        description = "各板块申赎处于正常配置区间，资金进出相对均衡，未见超常规干预。"
    else:
        label = "市场自发"
        description = "ETF 申赎主要由市场机构与散户自发驱动，国家队资金处于观望与蓄力状态。"

    return NationalTeamSupportScore(
        score=total_score,
        status=status,
        label=label,
        description=description,
        net_flow_factor=round(net_flow_factor, 1),
        breadth_factor=breadth_factor,
        divergence_factor=round(divergence_factor, 1),
        confidence=_support_confidence(
            summary,
            stale=stale,
            calendar_degraded=calendar_degraded,
        ),
    )


def _support_confidence(
    summary: NationalTeamSummary,
    *,
    stale: bool,
    calendar_degraded: bool,
) -> float:
    """由覆盖率与新鲜度推导托底评分的置信度。

    - 覆盖率：只有一部分 ETF 有份额时，资金因子与扩散因子都不可靠；
    - ``stale``：份额停在上一交易日，评的是“昨天”的盘面；
    - ``calendar_degraded``：连今天是不是交易日都无法确认，进一步打折。
    """
    coverage = max(0.0, min(1.0, summary.coverage_ratio))
    freshness = 0.35 if stale else 1.0
    calendar = 0.7 if calendar_degraded else 1.0
    return round(coverage * freshness * calendar, 2)


def _build_support_history(
    daily_flows: list[NationalTeamDailyFlow],
    indices: list[NationalTeamIndexSeries],
    etfs: list[NationalTeamEtfSeries],
) -> list[NationalTeamSupportHistoryPoint]:
    """用已算出的序列回算每个交易日的托底评分，不额外落库。

    每一天都用“当天及以前”的切片重跑同一套因子，而不是拿今天的分数向前填充：
    否则走势图只会是一条水平线。切片是按日滚动的，所以 5 日资金因子、沪深300
    两日涨跌都会自然随时间移动。
    """
    if not daily_flows:
        return []

    total_etfs = len(ETF_POOL) or 1
    coverage_by_date: dict[str, int] = {}
    for item in etfs:
        for point in item.points:
            coverage_by_date[point.date] = coverage_by_date.get(point.date, 0) + 1

    history: list[NationalTeamSupportHistoryPoint] = []
    for index, flow in enumerate(daily_flows):
        covered = coverage_by_date.get(flow.date, 0)
        # 没有任何成员数据、也没有可归因资金流的日子不进走势图，避免伪造 0 分。
        if covered == 0 and flow.total_flow_100m is None:
            continue
        coverage = round(covered / total_etfs, 4)
        window = daily_flows[max(0, index - 4) : index + 1]
        summary = NationalTeamSummary(
            estimated_net_flow_1d_100m=flow.total_flow_100m,
            estimated_net_flow_5d_100m=_sum_or_none([item.total_flow_100m for item in window]),
            coverage_ratio=coverage,
        )
        sliced_indices = [
            series.model_copy(
                update={"points": [point for point in series.points if point.date <= flow.date]}
            )
            for series in indices
        ]
        score = _calculate_support_score(summary, daily_flows[: index + 1], sliced_indices)
        history.append(
            NationalTeamSupportHistoryPoint(
                date=flow.date,
                score=score.score,
                status=score.status,
                confidence=score.confidence,
                coverage_ratio=coverage,
            )
        )
    return history


_BACKTEST_HORIZONS = (5, 20)
_BACKTEST_STATUSES = ("neutral", "moderate", "active", "strong")


def _forward_return(window: list[dict], index: int, horizon: int) -> float | None:
    """信号日之后第 horizon 个有收盘价的交易日的涨跌幅（%）。"""
    start = window[index].get("csi300_close")
    if start is None or start <= 0:
        return None
    future_closes = [
        row["csi300_close"]
        for row in window[index + 1 :]
        if row.get("csi300_close") is not None
    ]
    if len(future_closes) < horizon:
        return None
    return (future_closes[horizon - 1] / start - 1) * 100


def _horizon_stats(values: list[float], horizon: int) -> NationalTeamBacktestHorizon:
    if not values:
        return NationalTeamBacktestHorizon(days=horizon, samples=0)
    return NationalTeamBacktestHorizon(
        days=horizon,
        samples=len(values),
        avg_return_pct=round(statistics.fmean(values), 2),
        median_return_pct=round(statistics.median(values), 2),
        win_rate_pct=round(sum(1 for value in values if value > 0) / len(values) * 100, 1),
        best_return_pct=round(max(values), 2),
        worst_return_pct=round(min(values), 2),
    )


def build_support_backtest(
    rows: list[dict],
    *,
    window_samples: int = 365,
    min_confidence: float = 0.5,
    min_coverage: float = 0.5,
) -> NationalTeamSupportBacktest:
    """用已落库的评分与沪深300 收盘计算信号后 5/20 日表现。

    Args:
        rows: 按日期升序的评分快照，至少含 ``date`` / ``status`` /
            ``confidence`` / ``coverage_ratio`` / ``csi300_close``。
        window_samples: 只取最近多少个评分快照（一个交易日一条）。
        min_confidence: 低于该置信度的信号不进入回测，避免用残缺数据得出“高胜率”。
        min_coverage: 低于该 ETF 覆盖率的信号不进入回测。
    """
    window = rows[-window_samples:] if window_samples > 0 else rows
    eligible: list[dict] = []
    excluded_low_confidence = 0
    excluded_low_coverage = 0
    for row in window:
        confidence = row.get("confidence")
        coverage = row.get("coverage_ratio")
        if confidence is not None and float(confidence) < min_confidence:
            excluded_low_confidence += 1
            continue
        if coverage is not None and float(coverage) < min_coverage:
            excluded_low_coverage += 1
            continue
        eligible.append(row)

    sampled = [row for row in eligible if row.get("csi300_close") is not None]
    sample_days = len(sampled)

    horizons: list[NationalTeamBacktestHorizon] = []
    by_status: list[NationalTeamBacktestStatus] = []
    five_day: dict[str, list[float]] = {}
    for horizon in _BACKTEST_HORIZONS:
        returns_by_status: dict[str, list[float]] = {status: [] for status in _BACKTEST_STATUSES}
        for index, row in enumerate(eligible):
            value = _forward_return(eligible, index, horizon)
            if value is None:
                continue
            returns_by_status.setdefault(str(row.get("status")), []).append(value)
        all_values = [value for values in returns_by_status.values() for value in values]
        horizons.append(_horizon_stats(all_values, horizon))
        if horizon == 5:
            five_day = returns_by_status
        else:
            for status in _BACKTEST_STATUSES:
                five_values = five_day.get(status, [])
                twenty_values = returns_by_status.get(status, [])
                by_status.append(
                    NationalTeamBacktestStatus(
                        status=status,
                        samples=len(twenty_values),
                        avg_return_5d_pct=round(statistics.fmean(five_values), 2) if five_values else None,
                        avg_return_20d_pct=round(statistics.fmean(twenty_values), 2) if twenty_values else None,
                        win_rate_5d_pct=(
                            round(sum(1 for value in five_values if value > 0) / len(five_values) * 100, 1)
                            if five_values
                            else None
                        ),
                        win_rate_20d_pct=(
                            round(sum(1 for value in twenty_values if value > 0) / len(twenty_values) * 100, 1)
                            if twenty_values
                            else None
                        ),
                    )
                )

    note = ""
    if sample_days < max(_BACKTEST_HORIZONS) + 1:
        note = "样本不足：至少需要 21 个有沪深300 收盘的交易日才能评估 20 日表现。"
    elif horizons and horizons[-1].samples < 5:
        note = "20 日样本不足 5 个，长周期结果仅作参考。"

    return NationalTeamSupportBacktest(
        as_of_date=sampled[-1]["date"] if sampled else None,
        window_samples=window_samples,
        sample_days=sample_days,
        excluded_low_confidence=excluded_low_confidence,
        excluded_low_coverage=excluded_low_coverage,
        first_sample_date=sampled[0]["date"] if sampled else None,
        last_sample_date=sampled[-1]["date"] if sampled else None,
        horizons=horizons,
        by_status=by_status,
        note=note,
    )


def _score_percentile(
    history: list[NationalTeamSupportHistoryPoint],
    current: float,
    *,
    window: int = 60,
    min_samples: int = 60,
) -> float | None:
    """当前分数在最近 window 个交易日中的分位（0–100）。

    不改变评分阈值，只告诉用户「这个分数放在近期是什么水平」。样本不足 60 日时
    返回 None：字段叫 ``percentile_60d`` 就必须真的覆盖 60 个交易日，不能用 20 天
    冒充。
    """
    samples = [point.score for point in history[-window:]]
    if len(samples) < min_samples:
        return None
    below = sum(1 for value in samples if value < current)
    equal = sum(1 for value in samples if value == current)
    # 中位秩：全平时返回 50%，而不是把“没有变化”说成 100 分位。
    return round((below + 0.5 * equal) / len(samples) * 100, 1)


def _calculate_support_zones(indices: list[NationalTeamIndexSeries]) -> list[NationalTeamSupportZone]:
    """测算核心指数的国家队托底买入点位分布与加权成本中枢。"""
    target_keys = {"csi300", "sz50", "csi_a500"}
    results: list[NationalTeamSupportZone] = []

    for idx in indices:
        if idx.index_key not in target_keys or not idx.points:
            continue

        positive_points = [
            pt
            for pt in idx.points
            if (pt.estimated_net_flow_100m or 0.0) > 0.0 and pt.index_close and pt.index_close > 0
        ]

        current_price = idx.points[-1].index_close if idx.points else None
        if not positive_points:
            results.append(
                NationalTeamSupportZone(
                    index_key=idx.index_key,
                    index_name=idx.index_name,
                    current_price=current_price,
                    weighted_avg_cost=current_price,
                    cost_buffer_pct=0.0,
                    zones=[],
                )
            )
            continue

        total_flow = sum(pt.estimated_net_flow_100m for pt in positive_points if pt.estimated_net_flow_100m)
        if total_flow <= 0:
            weighted_cost = current_price
        else:
            weighted_cost = round(
                sum((pt.estimated_net_flow_100m or 0.0) * (pt.index_close or 0.0) for pt in positive_points)
                / total_flow,
                2,
            )

        buffer_pct = None
        if current_price and weighted_cost and weighted_cost > 0:
            buffer_pct = round(((current_price - weighted_cost) / weighted_cost) * 100, 2)

        prices = [pt.index_close for pt in positive_points if pt.index_close]
        min_p = min(prices)
        max_p = max(prices)
        spread = max(1.0, max_p - min_p)
        step = max(50.0, round(spread / 4, -1))

        base = round(min_p / step) * step
        bin_edges = [base + i * step for i in range(5)]
        bins_data: dict[str, tuple[float, float]] = {}

        for pt in positive_points:
            p = pt.index_close or 0.0
            f = pt.estimated_net_flow_100m or 0.0
            if p < bin_edges[1]:
                lbl = f"<{int(bin_edges[1])}"
                lower = float("-inf")
            elif p < bin_edges[2]:
                lbl = f"{int(bin_edges[1])}-{int(bin_edges[2])}"
                lower = bin_edges[1]
            elif p < bin_edges[3]:
                lbl = f"{int(bin_edges[2])}-{int(bin_edges[3])}"
                lower = bin_edges[2]
            elif p < bin_edges[4]:
                lbl = f"{int(bin_edges[3])}-{int(bin_edges[4])}"
                lower = bin_edges[3]
            else:
                lbl = f"≥{int(bin_edges[4])}"
                lower = bin_edges[4]
            bins_data[lbl] = (lower, bins_data.get(lbl, (lower, 0.0))[1] + f)

        # 按价格下界排序，避免 dict 插入顺序把高位区间排到低位区间前面。
        zones = [
            NationalTeamSupportZoneItem(
                range_label=lbl,
                net_flow_100m=round(flow, 2),
                share_pct=round((flow / total_flow * 100), 1) if total_flow > 0 else 0.0,
            )
            for lbl, (_, flow) in sorted(bins_data.items(), key=lambda item: item[1][0])
        ]

        results.append(
            NationalTeamSupportZone(
                index_key=idx.index_key,
                index_name=idx.index_name,
                current_price=current_price,
                weighted_avg_cost=weighted_cost,
                cost_buffer_pct=buffer_pct,
                zones=zones,
            )
        )

    return results


def build_national_team_response(
    *,
    share_history: dict[str, dict[str, float]],
    etf_close_history: dict[str, dict[str, float]],
    index_close_history: dict[str, dict[str, float]],
    fetched_at: str,
    requested_days: int,
    expected_trading_dates: list[str] | None = None,
    calendar_degraded: bool = False,
    share_metadata: dict[str, dict[str, dict]] | None = None,
    observations: list[NationalTeamShareObservation] | None = None,
    etf_amount_history: dict[str, dict[str, float]] | None = None,
    portrait: NationalTeamPortrait | None = None,
) -> NationalTeamResponse:
    """将份额与行情映射转换为 API 响应；该函数保持纯计算以便测试。"""
    share_dates = {day for code in ETF_POOL for day in share_history.get(code, {})}
    price_dates = {
        day for history in (etf_close_history, index_close_history) for values in history.values() for day in values
    }
    calendar_degraded = calendar_degraded or expected_trading_dates is None
    expected_dates = share_dates | price_dates | set(expected_trading_dates or [])
    expected_date = max(expected_trading_dates or [], default=None)
    as_of_date = max(share_dates, default=None)
    dates = sorted(day for day in expected_dates if as_of_date and day <= as_of_date)
    etfs = [
        _build_etf_series(
            definition,
            share_history.get(code, {}),
            etf_close_history.get(code, {}),
            dates,
            (etf_amount_history or {}).get(code, {}),
        )
        for code, definition in ETF_POOL.items()
    ]
    indices = [
        _build_index_series(definition, etfs, index_close_history.get(key, {}), dates)
        for key, definition in INDEX_POOL.items()
    ]
    for item in etfs:
        for point in item.points:
            metadata = (share_metadata or {}).get(item.code, {}).get(point.date, {})
            point.source = metadata.get("source", "unknown")
            point.fetched_at = metadata.get("fetched_at")
            point.verification_status = metadata.get("verification_status", "unknown")
    if not expected_trading_dates and not price_dates:
        # 纯存量冷启动时不知道缺了哪些交易日，不把样本点数当交易日数。
        for item in [*etfs, *indices]:
            item.latest_change_1d_100m = None
            item.change_5d_100m = None
            item.change_20d_100m = None
            for point in item.points:
                point.shares_change_100m = None
                point.estimated_net_flow_100m = None
        for item in etfs:
            for point in item.points:
                point.shares_change_pct = None
        for item in indices:
            item.estimated_net_flow_1d_100m = None
    populated = [item for item in etfs if item.points and item.latest_date == as_of_date]
    missing_share_etfs = [
        code
        for code in ETF_POOL
        if not share_history.get(code) or not expected_dates.issubset(share_history.get(code, {}))
    ]
    missing_price_etfs = [
        code
        for code in ETF_POOL
        if not etf_close_history.get(code) or not expected_dates.issubset(etf_close_history.get(code, {}))
    ]
    missing_indices = [
        key
        for key in INDEX_POOL
        if not index_close_history.get(key) or not expected_dates.issubset(index_close_history.get(key, {}))
    ]
    missing_etfs = sorted(set(missing_share_etfs) | set(missing_price_etfs))
    stale = bool(expected_date and (as_of_date is None or as_of_date < expected_date))
    total_shares = _sum_or_none([item.latest_shares_100m for item in populated])
    coverage_ratio = round(len(populated) / len(ETF_POOL), 4) if ETF_POOL else 0.0
    summary_quality: Literal["complete", "partial", "insufficient"] = (
        "complete" if coverage_ratio >= 1.0 else "partial" if populated else "insufficient"
    )
    daily_flows: list[NationalTeamDailyFlow] = []
    running_cumulative_flow = 0.0
    has_cumulative_flow = False
    for day in dates:
        day_flows_by_index: dict[str, float] = {}
        day_flows_by_category: dict[str, float] = {}
        total_day_flow = 0.0
        total_day_shares_change = 0.0
        total_day_amount = 0.0
        has_day_flow = False
        has_day_change = False
        has_day_amount = False

        for etf in etfs:
            for pt in etf.points:
                if pt.date == day:
                    if pt.estimated_net_flow_100m is not None:
                        has_day_flow = True
                        flow_val = pt.estimated_net_flow_100m
                        total_day_flow += flow_val
                        day_flows_by_index[etf.index_name] = round(
                            day_flows_by_index.get(etf.index_name, 0.0) + flow_val, 4
                        )
                        day_flows_by_category[etf.category] = round(
                            day_flows_by_category.get(etf.category, 0.0) + flow_val, 4
                        )
                    if pt.shares_change_100m is not None:
                        has_day_change = True
                        total_day_shares_change += pt.shares_change_100m
                    if pt.amount_100m is not None:
                        has_day_amount = True
                        total_day_amount += pt.amount_100m

        if has_day_flow:
            running_cumulative_flow += total_day_flow
            has_cumulative_flow = True

        bench_close = index_close_history.get("csi300", {}).get(day)
        if bench_close is None:
            for idx_closes in index_close_history.values():
                if day in idx_closes:
                    bench_close = idx_closes[day]
                    break

        daily_flows.append(
            NationalTeamDailyFlow(
                date=day,
                total_flow_100m=round(total_day_flow, 4) if has_day_flow else None,
                total_shares_change_100m=round(total_day_shares_change, 4) if has_day_change else None,
                total_amount_100m=round(total_day_amount, 4) if has_day_amount else None,
                cumulative_flow_100m=round(running_cumulative_flow, 4) if has_cumulative_flow else None,
                benchmark_close=round(bench_close, 2) if bench_close is not None else None,
                flows_by_index=day_flows_by_index,
                flows_by_category=day_flows_by_category,
            )
        )

    latest_day_flow = daily_flows[-1] if daily_flows else None
    top_cat = None
    top_idx = None
    if latest_day_flow:
        if latest_day_flow.flows_by_category:
            top_cat = max(latest_day_flow.flows_by_category.items(), key=lambda x: x[1])[0]
        if latest_day_flow.flows_by_index:
            top_idx = max(latest_day_flow.flows_by_index.items(), key=lambda x: x[1])[0]

    current_year = as_of_date[:4] if as_of_date else (dates[-1][:4] if dates else None)
    ytd_flows = [
        item.total_flow_100m
        for item in daily_flows
        if current_year and item.date.startswith(current_year) and item.total_flow_100m is not None
    ]
    ytd_net_flow = round(sum(ytd_flows), 4) if ytd_flows else None

    summary = NationalTeamSummary(
        total_shares_100m=total_shares,
        change_1d_100m=_sum_or_none([item.latest_change_1d_100m for item in populated]),
        change_5d_100m=_sum_or_none([item.change_5d_100m for item in populated]),
        change_20d_100m=_sum_or_none([item.change_20d_100m for item in populated]),
        estimated_net_flow_1d_100m=_sum_or_none(
            [item.points[-1].estimated_net_flow_100m if item.points else None for item in populated]
        ),
        estimated_net_flow_5d_100m=_sum_or_none([_period_flow(item.points, dates, 5) for item in populated]),
        estimated_net_flow_20d_100m=_sum_or_none([_period_flow(item.points, dates, 20) for item in populated]),
        coverage_ratio=coverage_ratio,
        quality=summary_quality,
        total_amount_1d_100m=latest_day_flow.total_amount_100m if latest_day_flow else None,
        cumulative_net_flow_100m=latest_day_flow.cumulative_flow_100m if latest_day_flow else None,
        ytd_net_flow_100m=ytd_net_flow,
        top_flow_category=top_cat,
        top_flow_index=top_idx,
    )
    support_score = _calculate_support_score(
        summary,
        daily_flows,
        indices,
        stale=stale,
        calendar_degraded=calendar_degraded,
    )
    support_score_history = _build_support_history(daily_flows, indices, etfs)
    percentile = _score_percentile(support_score_history, support_score.score)
    if percentile is not None:
        support_score = support_score.model_copy(update={"percentile_60d": percentile})
    support_zones = _calculate_support_zones(indices)
    return NationalTeamResponse(
        fetched_at=fetched_at,
        as_of_date=as_of_date,
        requested_days=requested_days,
        observations=observations or [],
        partial=bool(missing_etfs or missing_indices or stale or calendar_degraded),
        expected_date=expected_date,
        stale=stale,
        calendar_degraded=calendar_degraded,
        missing_share_etfs=missing_share_etfs,
        missing_price_etfs=missing_price_etfs,
        missing_indices=missing_indices,
        covered_etf_count=len(populated),
        total_etf_count=len(ETF_POOL),
        missing_etfs=missing_etfs,
        methodology=METHOD,
        disclaimer=DISCLAIMER,
        summary=summary,
        daily_flows=daily_flows,
        support_score=support_score,
        support_score_history=support_score_history,
        support_zones=support_zones,
        milestones=NATIONAL_TEAM_MILESTONES,
        portrait=portrait or DEFAULT_NATIONAL_TEAM_PORTRAIT,
        intraday=DEFAULT_NATIONAL_TEAM_INTRADAY,
        indices=indices,
        etfs=etfs,
    )
