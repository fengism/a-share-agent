"""行业资金流向剪刀差（主力出货/散户接盘）因子。"""

from __future__ import annotations

import logging
from typing import Dict, Tuple

from app.financial_data.industry.research import call_industry_data
from app.modules.industry_classification.public import a_share_all_levels_mapping

logger = logging.getLogger(__name__)


def _get_level2_to_level1_mapping() -> Dict[str, str]:
    mapping = a_share_all_levels_mapping()
    l2_to_l1 = {
        item["level2"]: item["level1"]
        for item in mapping.values()
        if item.get("level2") and item.get("level1")
    }
    # 补充特定命名兜底
    l2_to_l1["银行Ⅱ"] = "银行"
    l2_to_l1["银行"] = "银行"
    return l2_to_l1


async def calculate_industry_fund_flow_factors() -> Tuple[
    Dict[str, float],
    Dict[str, Dict[str, float]],
    Dict[str, List[Dict[str, float]]],
]:
    """
    抓取行业资金流，聚合成 31 个申万一级行业的资金剪刀差评分及下属二级行业明细。
    返回:
        (flow_scores, industry_raw_flows, level2_details)
    """
    l2_to_l1 = _get_level2_to_level1_mapping()
    industry_raw_flows: Dict[str, Dict[str, float]] = {}
    level2_details: Dict[str, List[Dict[str, float]]] = {}

    try:
        raw_flows = await call_industry_data("industry_fund_flow")
    except Exception as exc:
        logger.warning("获取行业资金流数据失败: %s", exc)
        return {}, {}, {}

    for item in raw_flows:
        name = item.get("industry_name", "")
        clean_name = name.rstrip("Ⅱ").rstrip("Ⅲ")
        level1 = l2_to_l1.get(name) or l2_to_l1.get(clean_name)
        if not level1:
            continue

        m_net = float(item.get("main_net", 0.0))
        s_net = float(item.get("small_net", 0.0))
        chg = float(item.get("change_pct", 0.0))

        if level1 not in industry_raw_flows:
            industry_raw_flows[level1] = {
                "main_net": 0.0,
                "small_net": 0.0,
                "change_pct_sum": 0.0,
                "count": 0.0,
            }
            level2_details[level1] = []

        acc = industry_raw_flows[level1]
        acc["main_net"] += m_net
        acc["small_net"] += s_net
        acc["change_pct_sum"] += chg
        acc["count"] += 1.0

        # 记录二级行业特征
        level2_details[level1].append({
            "name": name,
            "main_net": m_net,
            "retail_net": s_net,
            "change_pct": chg,
            "diff": s_net - m_net,
        })

    # 计算均值与剪刀差得分
    flow_scores: Dict[str, float] = {}
    divergences: Dict[str, float] = {}

    for ind, data in industry_raw_flows.items():
        if data["count"] > 0:
            data["change_pct"] = round(data["change_pct_sum"] / data["count"], 2)
        else:
            data["change_pct"] = 0.0

        # 剪刀差：小单净流入 - 主力净流入
        # 如果 small_net > 0 且 main_net < 0，diff 为正大值
        diff = data["small_net"] - data["main_net"]
        divergences[ind] = diff

    if not divergences:
        return {}, industry_raw_flows, level2_details

    # 时序/截面标准化：按当前所有申万行业的剪刀差排名与极值映射到 10 - 90
    min_diff = min(divergences.values())
    max_diff = max(divergences.values())
    diff_span = max(max_diff - min_diff, 1.0)

    for ind, diff in divergences.items():
        # 归一化到 10 - 90
        normalized = 10.0 + (diff - min_diff) / diff_span * 80.0

        # 结合涨跌幅做修正：
        # 若行业大涨 (>1.5%) 但主力大额净流出 (-main_net) 且散户狂买，加权强化
        data = industry_raw_flows[ind]
        if data.get("change_pct", 0.0) > 1.0 and data["main_net"] < 0 and data["small_net"] > 0:
            normalized = min(100.0, normalized + 12.0)
        elif data.get("change_pct", 0.0) < -1.5 and data["main_net"] > 0 and data["small_net"] < 0:
            # 跌停或深跌但主力逆向抄底、散户割肉出逃：韭菜指数大幅降低（黄金坑特征）
            normalized = max(0.0, normalized - 15.0)

        flow_scores[ind] = round(min(100.0, max(0.0, normalized)), 1)

    return flow_scores, industry_raw_flows, level2_details
