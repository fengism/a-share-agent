"""行业交易拥挤度与高位滞涨套牢风险因子。"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


def calculate_crowd_and_trap_factors(
    industry_raw_flows: Dict[str, Dict[str, float]],
    guba_scores: Dict[str, float],
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, list[str]]]:
    """
    根据行业资金流规模、涨跌幅、舆论热度计算：
    1. crowd_scores: 交易拥挤度 (0-100)
    2. trap_scores: 套牢风险度 (0-100)
    3. warning_signals: 预警特征标签
    """
    crowd_scores: Dict[str, float] = {}
    trap_scores: Dict[str, float] = {}
    warning_signals: Dict[str, list[str]] = {}

    for ind, data in industry_raw_flows.items():
        signals: list[str] = []
        change_pct = data.get("change_pct", 0.0)
        main_net = data.get("main_net", 0.0)
        small_net = data.get("small_net", 0.0)
        g_score = guba_scores.get(ind, 30.0)

        # 1. 拥挤度计算
        # 基础分来自舆论热度
        base_crowd = 0.6 * g_score + 20.0
        if change_pct > 2.5:
            base_crowd += 15.0
            signals.append("短线涨幅过大，短线投机资金极度聚集")
        elif change_pct < -2.0:
            base_crowd = max(10.0, base_crowd - 10.0)

        crowd_score = round(min(100.0, max(0.0, base_crowd)), 1)
        crowd_scores[ind] = crowd_score

        # 2. 高位滞涨与套牢风险计算
        # 特征1: 冲高滞涨 (涨幅微弱或平盘，但散户大举买入接盘)
        trap_score = 40.0
        if -0.5 <= change_pct <= 1.0 and small_net > 0 and main_net < 0:
            trap_score += 25.0
            signals.append("主力高位借流动性分流出货，滞涨信号明显")

        # 特征2: 深度回撤散户越跌越补
        if change_pct < -1.0 and small_net > 0:
            trap_score += 30.0
            signals.append("板块破位但散户逆势重仓补仓，上方形成沉重套牢盘")

        # 特征3: 舆论极度狂热
        if g_score >= 70.0:
            trap_score += 15.0
            signals.append("股吧讨论热度爆表，羊群效应处于极端区间")

        # 底部特征（出清）
        if change_pct < -2.0 and small_net < 0 and main_net > 0:
            trap_score = 15.0
            signals.append("散户恐慌割肉，主力低位承接，筹码有效出清")

        trap_score = round(min(100.0, max(0.0, trap_score)), 1)
        trap_scores[ind] = trap_score
        warning_signals[ind] = signals

    return crowd_scores, trap_scores, warning_signals
