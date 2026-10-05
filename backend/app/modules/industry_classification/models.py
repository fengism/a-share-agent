from __future__ import annotations

from datetime import date
from typing import Literal, cast

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.code_normalization import normalize_stock_identity

MarketGroup = Literal["A", "HK", "OVERSEAS"]


class IndustryRecordInput(BaseModel):
    market_group: MarketGroup
    exchange_suffix: str = Field(min_length=1, max_length=16)
    stock_code: str = Field(min_length=1, max_length=32)
    stock_name: str = Field(default="", max_length=128)
    sw_level1_name: str = Field(default="", max_length=128)
    sw_level2_name: str = Field(default="", max_length=128)
    sw_level3_name: str = Field(default="", max_length=128)
    sw_industry_code: str = Field(default="", max_length=32)
    source_version: str = Field(default="", max_length=128)
    effective_date: date | None = None

    @field_validator(
        "exchange_suffix",
        "stock_code",
        "stock_name",
        "sw_level1_name",
        "sw_level2_name",
        "sw_level3_name",
        "sw_industry_code",
        "source_version",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> str:
        return "" if value is None else str(value).strip()

    @field_validator("effective_date", mode="before")
    @classmethod
    def empty_effective_date_is_none(cls, value: object) -> object:
        # 历史/种子数据把缺失的 effective_date 存成空串，直接交给 date 解析会抛
        # ValidationError，导致整个 /stocks 列表 400。空串统一视为缺失。
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def normalize_identity(self) -> "IndustryRecordInput":
        code, exchange, market = normalize_stock_identity(
            self.stock_code,
            self.exchange_suffix if "exchange_suffix" in self.model_fields_set else "",
            self.market_group if "market_group" in self.model_fields_set else "",
        )
        self.stock_code = code
        self.exchange_suffix = exchange
        self.market_group = cast(MarketGroup, market)

        return self


class IndustryUpdateRequest(IndustryRecordInput):
    expected_revision: str = Field(min_length=64, max_length=64)


class IndustryRecord(IndustryRecordInput):
    revision: str
    id: int
    source: str
    is_manual_override: bool
    created_at: str
    updated_at: str


class IndustryListResponse(BaseModel):
    items: list[IndustryRecord]
    total: int
    page: int
    page_size: int


class IndustryHierarchyResponse(BaseModel):
    level1: list[str]
    level2: list[str]
    level3: list[str]


class IndustryStats(BaseModel):
    total: int
    market_counts: dict[str, int]
    level1_count: int
    level2_count: int
    level3_count: int
    latest_updated_at: str | None = None


class RefreshState(BaseModel):
    provider: str
    enabled: bool
    interval_seconds: int
    last_started_at: str | None = None
    last_succeeded_at: str | None = None
    last_failed_at: str | None = None
    last_error: str | None = None
    last_added: int
    last_updated: int
    last_unchanged: int
    updated_at: str


class IndustryStatusResponse(BaseModel):
    stats: IndustryStats
    refresh: RefreshState


class ImportFileRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)
    source_version: str = Field(default="", max_length=128)
    effective_date: date | None = None


class ImportPreviewResponse(BaseModel):
    import_token: str
    content_hash: str
    total_rows: int
    valid_rows: int
    added_rows: int
    updated_rows: int
    unchanged_rows: int
    skipped_rows: int
    conflict_rows: int
    invalid_rows: int
    warnings: list[str]
    sample: list[dict[str, object]]


class ImportCommitRequest(ImportFileRequest):
    import_token: str = Field(min_length=16, max_length=128)
    force_override: bool = False


class MutationResponse(BaseModel):
    success: bool = True
    id: int | None = None


class ImportCommitResponse(BaseModel):
    added: int
    updated: int
    unchanged: int
    skipped: int


class RefreshPolicyRequest(BaseModel):
    enabled: bool
    interval_seconds: int = Field(ge=3600, le=31 * 24 * 60 * 60)


class RefreshResponse(BaseModel):
    added: int
    updated: int
    unchanged: int
    provider: str
