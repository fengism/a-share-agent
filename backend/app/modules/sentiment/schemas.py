"""行业韭菜指数 Pydantic 契约定义。"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

RiskLevel = Literal["safe", "normal", "fever", "extreme"]


class LeekSubScores(BaseModel):
    """四个维度的子项评分 (0 - 100)"""
    flow: float = Field(..., description="资金背离度（主力出货/散户接盘剪刀差）")
    guba: float = Field(..., description="股吧散户热度与新晋关注度")
    crowd: float = Field(..., description="成交与交易拥挤度")
    trap: float = Field(..., description="高位滞涨与套牢盘风险")


class CrowdedStockItem(BaseModel):
    """散户跟风最集中的核心股票"""
    code: str
    name: str
    rank: Optional[int] = None
    change_pct: Optional[float] = None
    reason: Optional[str] = None


class SubIndustryLeekItem(BaseModel):
    """二级细分行业韭菜指数特征"""
    name: str = Field(..., description="二级行业名称，如 半导体、元件、消费电子")
    leek_score: float = Field(..., description="二级行业韭菜指数 (0-100)")
    change_pct: float = Field(default=0.0, description="二级行业涨跌幅 %")
    main_net: float = Field(default=0.0, description="主力净买入 (元)")
    retail_net: float = Field(default=0.0, description="散户净买入 (元)")


class IndustryLeekItem(BaseModel):
    """单个行业的韭菜指数详细特征"""
    industry_name: str = Field(..., description="申万一级行业名称")
    leek_score: float = Field(..., ge=0.0, le=100.0, description="综合韭菜指数 (0-100，越高越狂热/接盘)")
    risk_level: RiskLevel = Field(..., description="风险等级：safe(出清)/normal(均衡)/fever(过热)/extreme(见顶接盘)")
    sub_scores: LeekSubScores = Field(..., description="分维度得分")
    change_pct: float = Field(default=0.0, description="行业当日涨跌幅 %")
    main_net: float = Field(default=0.0, description="主力净买入额 (元)")
    retail_net: float = Field(default=0.0, description="散户/小单净买入额 (元)")
    crowded_stocks: List[CrowdedStockItem] = Field(default_factory=list, description="该行业人气最高/跟风最集中的代表股票")
    warning_signals: List[str] = Field(default_factory=list, description="预警信号特征列表")
    sub_industries: List[SubIndustryLeekItem] = Field(default_factory=list, description="下属申万二级细分行业分布")


class MarketLeekSummary(BaseModel):
    """全市场散户情绪整体画像"""
    median_score: float = Field(..., description="全市场行业韭菜指数中位数")
    extreme_count: int = Field(default=0, description="极度接盘区行业数 (score >= 75)")
    fever_count: int = Field(default=0, description="过热区行业数 (60 <= score < 75)")
    safe_count: int = Field(default=0, description="筹码出清/冷门区行业数 (score <= 35)")
    market_sentiment_label: str = Field(..., description="市场整体散户心理状态描述")


class LeekIndexOverviewResponse(BaseModel):
    """全行业韭菜指数总览响应"""
    trade_date: str = Field(..., description="数据日期 (YYYY-MM-DD)")
    updated_at: str = Field(..., description="更新时间戳")
    summary: MarketLeekSummary = Field(..., description="全市场汇总")
    industries: List[IndustryLeekItem] = Field(default_factory=list, description="行业列表（默认按韭菜指数从高到低排序）")


class LeekHistoryPoint(BaseModel):
    """单日历史数据点"""
    date: str
    score: float
    risk_level: RiskLevel
    sub_scores: LeekSubScores
    industry_change_pct: Optional[float] = None


class LeekIndexHistoryResponse(BaseModel):
    """单个行业的历史时序响应"""
    industry_name: str
    history: List[LeekHistoryPoint]
