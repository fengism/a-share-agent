"""东财股吧热度与粉丝跟风因子计算。"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import akshare as ak

from app.modules.industry_classification.public import a_share_all_levels_mapping
from app.modules.sentiment.schemas import CrowdedStockItem

logger = logging.getLogger(__name__)


def calculate_guba_sentiment_factors() -> Tuple[Dict[str, float], Dict[str, List[CrowdedStockItem]]]:
    """
    抓取东方财富股吧人气榜与飙升榜，按申万一级行业聚类。
    返回:
        (industry_guba_scores, industry_crowded_stocks)
        其中分数归一化到 0 - 100 之间。
    """
    mapping = a_share_all_levels_mapping()
    industry_hot_counts: Dict[str, int] = {}
    industry_up_counts: Dict[str, int] = {}
    industry_crowded_stocks: Dict[str, List[CrowdedStockItem]] = {}

    # 1. 抓取人气榜 Top 100
    try:
        hot_df = ak.stock_hot_rank_em()
        for _, row in hot_df.iterrows():
            raw_code = str(row.get("代码", ""))
            # 去除 SH/SZ 前缀提取 6 位纯代码
            clean_code = "".join(filter(str.isdigit, raw_code))
            name = str(row.get("股票名称", ""))
            rank = int(row.get("当前排名", 999))
            change_pct = float(row.get("涨跌幅", 0.0))

            info = mapping.get(clean_code)
            level1 = info.get("level1") if info else None
            if not level1:
                continue

            industry_hot_counts[level1] = industry_hot_counts.get(level1, 0) + 1
            if level1 not in industry_crowded_stocks:
                industry_crowded_stocks[level1] = []

            if len(industry_crowded_stocks[level1]) < 3:
                industry_crowded_stocks[level1].append(
                    CrowdedStockItem(
                        code=clean_code,
                        name=name,
                        rank=rank,
                        change_pct=change_pct,
                        reason="股吧人气Top100",
                    )
                )
    except Exception as exc:
        logger.warning("获取东方财富股吧人气榜失败，降级为默认基准值: %s", exc)

    # 2. 抓取飙升榜 Top 100
    try:
        up_df = ak.stock_hot_up_em()
        for _, row in up_df.iterrows():
            raw_code = str(row.get("代码", ""))
            clean_code = "".join(filter(str.isdigit, raw_code))
            name = str(row.get("股票名称", ""))
            rank_change = int(row.get("排名较昨日变动", 0))

            info = mapping.get(clean_code)
            level1 = info.get("level1") if info else None
            if not level1:
                continue

            industry_up_counts[level1] = industry_up_counts.get(level1, 0) + 1
            # 若该行业暂无代表股，补充飙升股
            if level1 not in industry_crowded_stocks or len(industry_crowded_stocks[level1]) < 3:
                if level1 not in industry_crowded_stocks:
                    industry_crowded_stocks[level1] = []
                # 避免重复加入
                if not any(s.code == clean_code for s in industry_crowded_stocks[level1]):
                    industry_crowded_stocks[level1].append(
                        CrowdedStockItem(
                            code=clean_code,
                            name=name,
                            change_pct=float(row.get("涨跌幅", 0.0)),
                            reason=f"人气排名暴涨+{rank_change}",
                        )
                    )
    except Exception as exc:
        logger.warning("获取东方财富股吧飙升榜失败: %s", exc)

    # 3. 计算 0 - 100 相对情绪分
    # 若某行业有 10 只股票进入人气榜（全市场共 100 只），则属于极度散户聚焦
    guba_scores: Dict[str, float] = {}
    for ind in set(list(industry_hot_counts.keys()) + list(industry_up_counts.keys())):
        hot_c = industry_hot_counts.get(ind, 0)
        up_c = industry_up_counts.get(ind, 0)
        # 基础分 20，每多一只人气股加 8 分，每多一只飙升股加 4 分，上限 100
        score = 20.0 + hot_c * 8.0 + up_c * 4.0
        guba_scores[ind] = min(100.0, max(0.0, score))

    return guba_scores, industry_crowded_stocks
