from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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

    @model_validator(mode="after")
    def normalize_identity(self) -> "IndustryRecordInput":
        self.exchange_suffix = self.exchange_suffix.upper()
        self.stock_code = self.stock_code.upper()
        if "." not in self.stock_code and self.market_group in {"A", "HK"}:
            self.stock_code = f"{self.stock_code}.{self.exchange_suffix}"
        return self


class IndustryRecord(IndustryRecordInput):
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
