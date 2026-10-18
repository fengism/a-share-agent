"""财务基本面二次重排。"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import date

from app.financial_data.stock.public import get_financial_metrics
from app.modules.potential.common import _float_or_none
from app.modules.potential.constants import (
    _FUNDAMENTAL_CANDIDATE_LIMIT,
    _FUNDAMENTAL_CONCURRENCY,
    _FUNDAMENTAL_MIN_SCORE,
    _FUNDAMENTAL_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


def _annualized_roe(roe: float | None, report_date: str | None) -> float | None:
    """把报告期 ROE 年化，便于不同披露期公司横向比较。"""
    if roe is None or not math.isfinite(roe):
        return None
    text = str(report_date or "")
    if "03-31" in text:
        factor = 4.0
    elif "06-30" in text:
        factor = 2.0
    elif "09-30" in text:
        factor = 4 / 3
    else:
        factor = 1.0
    annualized = roe * factor
    return annualized if math.isfinite(annualized) else None

def _fundamental_score(
    metrics: dict,
    report_date: str | None,
    industry: str | None = None,
) -> tuple[float, list[str], str]:
    """根据 ROE、增长、负债与现金流计算基本面分。"""
    is_financial = bool(industry and any(keyword in industry for keyword in ("金融", "银行", "保险", "证券")))
    equity = _float_or_none(metrics.get("股东权益"))
    negative_equity = equity is not None and equity <= 0
    roe = None if negative_equity else _annualized_roe(_float_or_none(metrics.get("净资产收益率")), report_date)
    profit_yoy = _float_or_none(metrics.get("净利润同比"))
    revenue_yoy = _float_or_none(metrics.get("营收同比"))
    debt_ratio = _float_or_none(metrics.get("资产负债率"))
    ocf_to_profit = _float_or_none(metrics.get("现净比"))
    if all(value is None for value in (roe, profit_yoy, revenue_yoy, debt_ratio, ocf_to_profit)) and not negative_equity:
        return 0.0, ["财务数据缺失"], ""

    score = 0.0
    flags: list[str] = []
    highlights: list[str] = []
    if negative_equity:
        score -= 0.3
        flags.append("净资产为负")
    if roe is not None:
        if roe >= 0.18:
            score += 0.5
            highlights.append(f"ROE {roe * 100:.1f}%")
        elif roe >= 0.12:
            score += 0.3
            highlights.append(f"ROE {roe * 100:.1f}%")
        elif roe >= 0.08:
            score += 0.15
        elif roe < 0:
            score -= 0.3
            flags.append("ROE为负")
        elif roe < 0.04:
            score -= 0.1
            flags.append("ROE偏低")
    if profit_yoy is not None:
        if profit_yoy >= 30:
            score += 0.4
            highlights.append(f"净利+{profit_yoy:.0f}%")
        elif profit_yoy >= 15:
            score += 0.25
        elif profit_yoy >= 5:
            score += 0.1
        elif profit_yoy < -30:
            score -= 0.35
            flags.append("净利大幅下滑")
        elif profit_yoy < 0:
            score -= 0.2
            flags.append("净利下滑")
    if revenue_yoy is not None:
        if revenue_yoy >= 20:
            score += 0.25
            highlights.append(f"营收+{revenue_yoy:.0f}%")
        elif revenue_yoy >= 8:
            score += 0.15
        elif revenue_yoy < 0:
            score -= 0.1
            flags.append("营收下滑")
    if debt_ratio is not None and not is_financial:
        if debt_ratio > 0.7:
            score -= 0.25
            flags.append("负债率偏高")
        elif debt_ratio > 0.6:
            score -= 0.1
        elif debt_ratio < 0.4:
            score += 0.1
    if ocf_to_profit is not None:
        if ocf_to_profit >= 1.0:
            score += 0.15
            highlights.append("现金流健康")
        elif ocf_to_profit < 0:
            score -= 0.2
            flags.append("经营现金流为负")
        elif ocf_to_profit < 0.5:
            score -= 0.15
            flags.append("现金转化偏弱")
    return round(max(-1.2, min(score, 1.5)), 2), list(dict.fromkeys(flags)), "，".join(highlights[:2])

async def _apply_fundamental_overlay(
    items: list[dict],
    market_date: date,
    limit: int = _FUNDAMENTAL_CANDIDATE_LIMIT,
) -> tuple[int, int]:
    """对技术评分靠前的候选补拉财务指标，做二次基本面重排。

    只使用报告期不晚于挖掘日的财务数据，避免历史回填时出现前视偏差。
    """
    if not items:
        return 0, 0
    ranked = sorted(items, key=lambda item: (-item.get("score", 0.0), -(item.get("amount") or 0)))
    targets = [item for item in ranked if item.get("score", 0.0) >= _FUNDAMENTAL_MIN_SCORE][:limit]
    if not targets:
        return 0, 0

    semaphore = asyncio.Semaphore(_FUNDAMENTAL_CONCURRENCY)
    succeeded = 0
    failed = 0

    async def enrich(item: dict) -> None:
        nonlocal succeeded, failed
        async with semaphore:
            try:
                metrics = await asyncio.wait_for(
                    get_financial_metrics(str(item["code"])),
                    timeout=_FUNDAMENTAL_TIMEOUT_SECONDS,
                )
            except Exception as error:
                failed += 1
                logger.debug("潜力股基本面获取失败 %s: %s", item.get("code"), error)
                if "财务数据缺失" not in item["risk_flags"]:
                    item["risk_flags"].append("财务数据缺失")
                return
        report_date = str(metrics.latest_report_date or "")[:10]
        if report_date and report_date > market_date.isoformat():
            failed += 1
            if "财务数据滞后" not in item["risk_flags"]:
                item["risk_flags"].append("财务数据滞后")
            return
        score, flags, summary = _fundamental_score(
            metrics.metrics,
            metrics.latest_report_date,
            item.get("industry"),
        )
        item["fundamental_score"] = score
        item["score"] = round(
            max(
                0.0,
                item.get("signal_score", 0.0)
                + item.get("quality_score", 0.0)
                + item.get("theme_score", 0.0)
                + score,
            ),
            2,
        )
        for flag in flags:
            if flag not in item["risk_flags"]:
                item["risk_flags"].append(flag)
        fundamental_bits: list[str] = []
        if summary:
            fundamental_bits.append(summary)
        if flags:
            fundamental_bits.append("基本面风险：" + "、".join(flags[:2]))
        if fundamental_bits:
            item["reason"] = f"{item['reason']}；{'；'.join(fundamental_bits)}"[:200]
        succeeded += 1

    await asyncio.gather(*(enrich(item) for item in targets))
    return succeeded, failed
