"""Shared industry-chain research scope contract."""

from datetime import date, timedelta
from typing import Literal, cast

from pydantic import BaseModel, Field, model_validator

from app.core.market import market_today


class IndustryChainResearchScope(BaseModel):
    region: Literal["china", "global", "china_and_global"] = "china_and_global"
    time_range: Literal["half_year", "one_year", "three_years", "custom"] = "half_year"
    start_date: date | None = None
    end_date: date | None = None
    as_of_date: date | None = None
    company_scope: Literal["a_share", "all_public"] = "a_share"
    refresh_dimensions: list[Literal["market", "stocks", "competition", "technology", "chain", "drivers_risks", "reports", "events"]] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_custom_range(self) -> "IndustryChainResearchScope":
        if self.time_range == "custom" and (self.start_date is None or self.end_date is None):
            raise ValueError("自定义时间范围必须同时提供开始日期和结束日期")
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise ValueError("开始日期不能晚于结束日期")
        self.refresh_dimensions = sorted(set(self.refresh_dimensions))
        return self


def resolve_industry_chain_scope(
    scope: IndustryChainResearchScope | None = None,
    *,
    today: date | None = None,
) -> IndustryChainResearchScope:
    current = scope or IndustryChainResearchScope()
    resolved_today = today or market_today()
    as_of_date = current.as_of_date or resolved_today
    if as_of_date > resolved_today:
        raise ValueError("分析基准日期不能晚于今天")
    if current.time_range == "custom":
        start_date = current.start_date
        end_date = current.end_date
    else:
        days = {"half_year": 183, "one_year": 365, "three_years": 1095}[current.time_range]
        start_date = as_of_date - timedelta(days=days)
        end_date = as_of_date
    if end_date is not None and end_date > as_of_date:
        raise ValueError("结束日期不能晚于分析基准日期")
    return cast(IndustryChainResearchScope, current.model_copy(update={
        "start_date": start_date,
        "end_date": end_date,
        "as_of_date": as_of_date,
    }))


def render_industry_chain_scope(scope: IndustryChainResearchScope) -> str:
    region = {
        "china": "中国",
        "global": "全球",
        "china_and_global": "中国与全球对比",
    }[scope.region]
    company_scope = "仅限 A 股上市公司映射" if scope.company_scope == "a_share" else "覆盖全部公开公司"
    return (
        f"区域口径：{region}；时间范围：{scope.start_date} 至 {scope.end_date}；"
        f"分析基准日：{scope.as_of_date}；公司范围：{company_scope}"
    )
