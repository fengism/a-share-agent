"""行业韭菜指数聚合与评分服务。"""

from __future__ import annotations

import asyncio
import logging
import statistics
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.configuration.paths import DATA_DIR
from app.financial_data.market.trading_session import SHANGHAI_TIMEZONE
from app.infrastructure.persistence.json_storage import atomic_write_text
from app.modules.industry_classification.public import hierarchy
from app.modules.sentiment.factors.crowd import calculate_crowd_and_trap_factors
from app.modules.sentiment.factors.flow import calculate_industry_fund_flow_factors
from app.modules.sentiment.factors.guba import calculate_guba_sentiment_factors
from app.modules.sentiment.schemas import (
    IndustryLeekItem,
    LeekHistoryPoint,
    LeekIndexHistoryResponse,
    LeekIndexOverviewResponse,
    LeekSubScores,
    MarketLeekSummary,
    RiskLevel,
    SubIndustryLeekItem,
)


def _get_today_str() -> str:
    return datetime.now(SHANGHAI_TIMEZONE).strftime("%Y-%m-%d")

logger = logging.getLogger(__name__)

_SENTIMENT_DATA_DIR = Path(DATA_DIR) / "sentiment" / "leek_index"


class LeekIndexService:
    def __init__(self) -> None:
        self._cached_overview: Optional[LeekIndexOverviewResponse] = None
        self._cache_time: float = 0.0
        self._cache_ttl_seconds: float = 30.0  # 盘中 30 秒缓存

    async def get_overview(self, force_refresh: bool = False) -> LeekIndexOverviewResponse:
        """获取全市场申万一级行业韭菜指数概览。"""
        now = datetime.now()
        now_ts = now.timestamp()
        today_str = _get_today_str()

        # 1. 检查内存缓存
        if not force_refresh and self._cached_overview and (now_ts - self._cache_time < self._cache_ttl_seconds):
            return self._cached_overview

        # 2. 检查本地持久化文件（若今日已归档且不需要强制刷新）
        persisted = self._load_persisted_result(today_str)
        if persisted and not force_refresh:
            self._cached_overview = persisted
            self._cache_time = now_ts
            return persisted

        # 3. 实时计算
        overview = await self._compute_overview(today_str)
        self._cached_overview = overview
        self._cache_time = now_ts

        # 4. 自动持久化当日结果
        self._persist_result(overview)
        return overview

    async def get_history(self, industry_name: str, days: int = 30) -> LeekIndexHistoryResponse:
        """获取指定行业的历史韭菜指数走势（用于双轴图绘制）。"""
        dates = self._list_persisted_dates(days)
        history_points: List[LeekHistoryPoint] = []

        for d in dates:
            data = self._load_persisted_result(d)
            if not data:
                continue
            item = next((ind for ind in data.industries if ind.industry_name == industry_name), None)
            if item:
                history_points.append(
                    LeekHistoryPoint(
                        date=d,
                        score=item.leek_score,
                        risk_level=item.risk_level,
                        sub_scores=item.sub_scores,
                        industry_change_pct=item.change_pct,
                    )
                )

        # 若历史数据积累较少，通过当前值模拟合理基线，确保前端图表正常渲染
        if not history_points:
            current = await self.get_overview()
            curr_item = next((ind for ind in current.industries if ind.industry_name == industry_name), None)
            if curr_item:
                history_points.append(
                    LeekHistoryPoint(
                        date=current.trade_date,
                        score=curr_item.leek_score,
                        risk_level=curr_item.risk_level,
                        sub_scores=curr_item.sub_scores,
                        industry_change_pct=curr_item.change_pct,
                    )
                )

        return LeekIndexHistoryResponse(
            industry_name=industry_name,
            history=sorted(history_points, key=lambda x: x.date),
        )

    async def _compute_overview(self, today_str: str) -> LeekIndexOverviewResponse:
        # 并发获取资金流与股吧情绪
        flow_task = calculate_industry_fund_flow_factors()
        guba_task = asyncio.to_thread(calculate_guba_sentiment_factors)

        (flow_scores, raw_flows, level2_details), (guba_scores, crowded_stocks) = await asyncio.gather(flow_task, guba_task)

        # 计算拥挤度与滞涨风险
        crowd_scores, trap_scores, warning_signals = calculate_crowd_and_trap_factors(raw_flows, guba_scores)

        # 获取申万 31 个一级行业名单
        level1_names = hierarchy().get("level1", [])
        all_industries = sorted(list(set(level1_names + list(raw_flows.keys()))))

        items: List[IndustryLeekItem] = []
        for ind in all_industries:
            s_flow = flow_scores.get(ind, 50.0)
            s_guba = guba_scores.get(ind, 30.0)
            s_crowd = crowd_scores.get(ind, 45.0)
            s_trap = trap_scores.get(ind, 40.0)

            # 综合评分: 资金背离30% + 股吧热度25% + 成交拥挤25% + 滞涨套牢20%
            final_score = round(0.30 * s_flow + 0.25 * s_guba + 0.25 * s_crowd + 0.20 * s_trap, 1)

            if final_score >= 75.0:
                risk_level: RiskLevel = "extreme"
            elif final_score >= 60.0:
                risk_level = "fever"
            elif final_score <= 35.0:
                risk_level = "safe"
            else:
                risk_level = "normal"

            raw_ind_flow = raw_flows.get(ind, {})

            # 格式化下属二级细分行业分布并估算二级行业韭菜指数
            sub_items: List[SubIndustryLeekItem] = []
            for l2 in level2_details.get(ind, []):
                # 以一级行业得分为基线，按二级行业资金剪刀差微调
                l2_diff = l2.get("diff", 0.0)
                l2_score = round(max(5.0, min(95.0, final_score + (10.0 if l2_diff > 0 else -10.0))), 1)
                sub_items.append(
                    SubIndustryLeekItem(
                        name=l2["name"],
                        leek_score=l2_score,
                        change_pct=round(l2.get("change_pct", 0.0), 2),
                        main_net=l2.get("main_net", 0.0),
                        retail_net=l2.get("retail_net", 0.0),
                    )
                )
            sub_items.sort(key=lambda x: x.leek_score, reverse=True)

            items.append(
                IndustryLeekItem(
                    industry_name=ind,
                    leek_score=final_score,
                    risk_level=risk_level,
                    sub_scores=LeekSubScores(
                        flow=s_flow,
                        guba=s_guba,
                        crowd=s_crowd,
                        trap=s_trap,
                    ),
                    change_pct=raw_ind_flow.get("change_pct", 0.0),
                    main_net=raw_ind_flow.get("main_net", 0.0),
                    retail_net=raw_ind_flow.get("small_net", 0.0),
                    crowded_stocks=crowded_stocks.get(ind, []),
                    warning_signals=warning_signals.get(ind, []),
                    sub_industries=sub_items,
                )
            )

        # 按韭菜指数从高到低排序
        items.sort(key=lambda x: x.leek_score, reverse=True)

        # 汇总全市场概况
        scores = [item.leek_score for item in items]
        median_score = round(float(statistics.median(scores)), 1) if scores else 50.0
        extreme_cnt = sum(1 for item in items if item.risk_level == "extreme")
        fever_cnt = sum(1 for item in items if item.risk_level == "fever")
        safe_cnt = sum(1 for item in items if item.risk_level == "safe")

        if median_score >= 65.0:
            label = "全市场散户情绪高度亢奋，多数行业呈现主力流出与散户追涨背离，警惕共振回调"
        elif median_score <= 40.0:
            label = "市场散户交投情绪低迷冰点，多数板块筹码充分沉淀出清，具备左侧配置价值"
        else:
            label = "全市场博弈相对均衡，局部热门题材有散户聚集现象，整体风险可控"

        return LeekIndexOverviewResponse(
            trade_date=today_str,
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            summary=MarketLeekSummary(
                median_score=median_score,
                extreme_count=extreme_cnt,
                fever_count=fever_cnt,
                safe_count=safe_cnt,
                market_sentiment_label=label,
            ),
            industries=items,
        )

    def _persist_result(self, overview: LeekIndexOverviewResponse) -> None:
        try:
            _SENTIMENT_DATA_DIR.mkdir(parents=True, exist_ok=True)
            path = _SENTIMENT_DATA_DIR / f"{overview.trade_date}.json"
            atomic_write_text(path, overview.model_dump_json(indent=2))
        except Exception as exc:
            logger.warning("保存韭菜指数历史记录失败: %s", exc)

    def _load_persisted_result(self, date_str: str) -> Optional[LeekIndexOverviewResponse]:
        path = _SENTIMENT_DATA_DIR / f"{date_str}.json"
        if not path.exists():
            return None
        try:
            return LeekIndexOverviewResponse.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _list_persisted_dates(self, limit: int = 30) -> List[str]:
        if not _SENTIMENT_DATA_DIR.exists():
            return []
        dates = sorted(
            [p.stem for p in _SENTIMENT_DATA_DIR.glob("*.json") if p.stem.count("-") == 2],
            reverse=True,
        )
        return dates[:limit]


_leek_service: Optional[LeekIndexService] = None


def get_leek_index_service() -> LeekIndexService:
    global _leek_service
    if _leek_service is None:
        _leek_service = LeekIndexService()
    return _leek_service
