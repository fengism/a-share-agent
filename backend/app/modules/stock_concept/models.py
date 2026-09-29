from __future__ import annotations

from typing import Literal, cast

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.code_normalization import normalize_stock_identity

MarketGroup = Literal["A", "HK", "OVERSEAS"]


class StockConceptRecordInput(BaseModel):
    market_group: MarketGroup = "A"
    exchange_suffix: str = Field(min_length=1, max_length=16, default="SZ")
    stock_code: str = Field(min_length=1, max_length=32)
    stock_name: str = Field(default="", max_length=128)
    concepts: list[str] = Field(default_factory=list)
    source_version: str = Field(default="", max_length=128)

    @field_validator("exchange_suffix", "stock_code", "stock_name", "source_version", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> str:
        return "" if value is None else str(value).strip()

    @field_validator("concepts", mode="before")
    @classmethod
    def normalize_concepts(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            parts = [p.strip() for p in value.replace("；", ";").replace(",", ";").replace("，", ";").split(";")]
            return [p for p in parts if p]
        if isinstance(value, (list, tuple, set)):
            result: list[str] = []
            seen: set[str] = set()
            for item in value:
                s = str(item).strip()
                if s and s not in seen:
                    seen.add(s)
                    result.append(s)
            return result
        return []

    @model_validator(mode="after")
    def normalize_identity(self) -> "StockConceptRecordInput":
        code, exchange, market = normalize_stock_identity(
            self.stock_code,
            self.exchange_suffix if "exchange_suffix" in self.model_fields_set else "",
            self.market_group if "market_group" in self.model_fields_set else "",
        )
        self.stock_code = code
        self.exchange_suffix = exchange
        self.market_group = cast(MarketGroup, market)

        return self


class StockConceptUpdateRequest(StockConceptRecordInput):
    expected_revision: str = Field(min_length=64, max_length=64)


class StockConceptRecord(StockConceptRecordInput):
    revision: str
    id: int
    source: str
    is_manual_override: bool
    created_at: str
    updated_at: str


class StockConceptListResponse(BaseModel):
    items: list[StockConceptRecord]
    total: int
    page: int
    page_size: int


class ConceptItem(BaseModel):
    name: str
    stock_count: int


class ConceptListResponse(BaseModel):
    items: list[ConceptItem]
    total: int


class ConceptStats(BaseModel):
    total_stocks: int
    total_concepts: int
    market_counts: dict[str, int]
    latest_updated_at: str | None = None


class ConceptStatusResponse(BaseModel):
    stats: ConceptStats


class ConceptImportFileRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1)
    source_version: str = Field(default="", max_length=128)


class ConceptImportPreviewResponse(BaseModel):
    import_token: str
    content_hash: str
    total_rows: int
    valid_rows: int
    added_rows: int
    updated_rows: int
    unchanged_rows: int
    skipped_rows: int
    invalid_rows: int
    warnings: list[str]
    sample: list[dict[str, object]]


class ConceptImportCommitRequest(ConceptImportFileRequest):
    import_token: str = Field(min_length=16, max_length=128)
    force_override: bool = False


class ConceptImportCommitResponse(BaseModel):
    added: int
    updated: int
    unchanged: int
    skipped: int


class ConceptMutationResponse(BaseModel):
    success: bool = True
    id: int | None = None
