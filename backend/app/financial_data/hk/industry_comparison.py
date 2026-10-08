"""港股行业对比服务（基于同花顺 F10 行业地位与同业公司数据）。"""

from __future__ import annotations

import logging
from typing import Any, cast

from pydantic import BaseModel, Field

from app.core.cache import dated_cache_key
from app.core.cache import market_cache as cache
from app.core.concurrency.rate_limiter import ths_semaphore
from app.core.concurrency.singleflight import AsyncSingleFlight
from app.core.exceptions import UpstreamUnavailableError
from app.financial_data.hk.service import normalize_hk_code
from app.infrastructure.providers.provider_gateway import provider_gateway
from app.infrastructure.providers.registry import get_provider

logger = logging.getLogger(__name__)

_INDUSTRY_COMPARISON_CACHE_TTL = 86400  # 财务报告期对比数据更新频率低，缓存 24 小时
_comparison_singleflight: AsyncSingleFlight[HKIndustryComparison] = AsyncSingleFlight()


class HKIndustryPeerItem(BaseModel):
    """单个同业竞争公司的关键财务与估值对比指标。"""

    code: str
    name: str = ""
    total_shares: float | None = None  # 总股本（亿股）
    total_assets: float | None = None  # 资产总计（亿元）
    pe: float | None = None  # 市盈率
    is_pe_loss: bool = False  # 是否亏损
    pb: float | None = None  # 市净率
    current_assets: float | None = None  # 流动资产（亿元）
    total_liabilities: float | None = None  # 负债合计（亿元）
    debt_to_assets_ratio: float | None = None  # 资产负债率（%）
    net_profit: float | None = None  # 税后利润（亿元）


class HKIndustryComparison(BaseModel):
    """港股所属行业分类与同业公司对比总览。"""

    code: str
    industry: str = ""  # 一级行业
    sub_industry: str = ""  # 二级行业
    segment: str = ""  # 三级细分行业
    industry_path: str = ""  # 完整行业层级路径
    company_count: int = 0  # 行业公司总数
    periods: list[str] = Field(default_factory=list)  # 可用报告期列表
    current_period: str | None = None  # 当前展示的报告期
    peers: list[HKIndustryPeerItem] = Field(default_factory=list)  # 当前报告期的同行指标列表
    all_period_data: dict[str, list[HKIndustryPeerItem]] = Field(default_factory=dict)  # 所有报告期明细
    source: str = "ths"
    source_url: str = ""


async def _fetch_hk_industry_comparison_remote(code: str) -> HKIndustryComparison:
    provider = get_provider("ths")
    try:
        raw: dict[str, Any] = await provider_gateway.call_blocking(
            "ths",
            "hk_industry_comparison",
            provider.fetch_hk_industry_comparison,
            code,
            semaphore=ths_semaphore,
        )
    except Exception as exc:
        raise UpstreamUnavailableError(f"同花顺港股行业对比接口暂不可用: {exc}") from exc

    norm_code = normalize_hk_code(code)
    periods = raw.get("periods") or []
    current_period = periods[0] if periods else None

    all_period_data: dict[str, list[HKIndustryPeerItem]] = {}
    for period_name, rows in (raw.get("period_data") or {}).items():
        all_period_data[period_name] = [
            HKIndustryPeerItem.model_validate(row) for row in rows
        ]

    peers = all_period_data.get(current_period, []) if current_period else []

    return HKIndustryComparison(
        code=norm_code,
        industry=raw.get("industry") or "",
        sub_industry=raw.get("sub_industry") or "",
        segment=raw.get("segment") or "",
        industry_path=raw.get("industry_path") or "",
        company_count=raw.get("company_count") or len(peers),
        periods=periods,
        current_period=current_period,
        peers=peers,
        all_period_data=all_period_data,
        source=raw.get("source") or "ths",
        source_url=raw.get("source_url") or "",
    )


async def get_hk_stock_industry_comparison(
    code: str,
    period: str | None = None,
) -> HKIndustryComparison:
    """获取港股所属行业分类与同业公司对比数据（支持按报告期切换）。"""
    norm_code = normalize_hk_code(code)
    cache_key = dated_cache_key("hk_industry_comparison", norm_code)
    cached = cache.get(cache_key)

    result: HKIndustryComparison
    if cached is not None:
        result = HKIndustryComparison.model_validate(cached)
    else:
        async def load_and_cache() -> HKIndustryComparison:
            data = await _fetch_hk_industry_comparison_remote(norm_code)
            cache.set(cache_key, data, ttl=_INDUSTRY_COMPARISON_CACHE_TTL)
            return data

        result = cast(HKIndustryComparison, await _comparison_singleflight.do(cache_key, load_and_cache))

    if period and period in result.all_period_data:
        # 复制并切换指定报告期
        return cast(
            HKIndustryComparison,
            result.model_copy(
                update={
                    "current_period": period,
                    "peers": result.all_period_data[period],
                }
            ),
        )
    return result


__all__ = [
    "HKIndustryComparison",
    "HKIndustryPeerItem",
    "get_hk_stock_industry_comparison",
]
