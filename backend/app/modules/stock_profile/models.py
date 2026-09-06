from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.market import classify_exchange

MarketGroup = Literal["A", "HK", "OVERSEAS"]


class StockBasicProfileInput(BaseModel):
    market_group: MarketGroup = "A"
    exchange: str = Field(default="", max_length=16)
    board: str = Field(default="", max_length=32)
    stock_code: str = Field(min_length=1, max_length=32)
    stock_name: str = Field(default="", max_length=128)
    listing_date: str | None = Field(default=None, max_length=32)
    main_business: str = Field(default="")
    business_scope: str = Field(default="")
    products: str = Field(default="")
    industry: str = Field(default="", max_length=128)
    sw_level1_name: str = Field(default="", max_length=64)
    sw_level2_name: str = Field(default="", max_length=64)
    sw_level3_name: str = Field(default="", max_length=64)
    city: str = Field(default="", max_length=64)
    province: str = Field(default="", max_length=64)
    legal_repr: str = Field(default="", max_length=64)
    registered_capital: str = Field(default="", max_length=64)
    setup_date: str | None = Field(default=None, max_length=32)
    website: str = Field(default="", max_length=256)
    company_intro: str = Field(default="")
    source_version: str = Field(default="", max_length=128)

    @field_validator(
        "exchange",
        "board",
        "stock_code",
        "stock_name",
        "listing_date",
        "main_business",
        "business_scope",
        "products",
        "industry",
        "sw_level1_name",
        "sw_level2_name",
        "sw_level3_name",
        "city",
        "province",
        "legal_repr",
        "registered_capital",
        "setup_date",
        "website",
        "company_intro",
        "source_version",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> str:
        return "" if value is None else str(value).strip()

    @model_validator(mode="after")
    def normalize_identity(self) -> "StockBasicProfileInput":
        self.stock_code = self.stock_code.strip().upper()
        if not self.exchange:
            if "." in self.stock_code:
                self.exchange = self.stock_code.split(".", 1)[1]
            elif self.market_group == "A":
                raw_digits = self.stock_code.split(".")[0]
                if len(raw_digits) == 6 and raw_digits.isdigit():
                    try:
                        self.exchange = classify_exchange(raw_digits)
                    except ValueError:
                        self.exchange = "SH" if raw_digits.startswith("6") else "SZ"
            elif self.market_group == "HK":
                self.exchange = "HK"

        self.exchange = self.exchange.upper()
        if "." not in self.stock_code and self.market_group in {"A", "HK"} and self.exchange:
            self.stock_code = f"{self.stock_code}.{self.exchange}"

        if not self.board and self.market_group == "A":
            raw_code = self.stock_code.split(".")[0]
            if raw_code.startswith("688"):
                self.board = "科创板"
            elif raw_code.startswith("30"):
                self.board = "创业板"
            elif raw_code.startswith(("4", "8", "920")):
                self.board = "北交所"
            elif self.exchange == "SH":
                self.board = "主板"
            elif self.exchange == "SZ":
                self.board = "主板"
        elif not self.board and self.market_group == "HK":
            self.board = "港股主板"

        return self


class StockBasicProfileRecord(StockBasicProfileInput):
    id: int
    source: str
    is_manual_override: bool
    created_at: str
    updated_at: str


class StockBasicProfileListResponse(BaseModel):
    items: list[StockBasicProfileRecord]
    total: int
    page: int
    page_size: int


class StockBasicProfileSummary(BaseModel):
    total: int
    has_business_count: int
    has_listing_date_count: int
    market_group_counts: dict[str, int]
    board_counts: dict[str, int]
    last_updated_at: str | None


class StockProfileEnrichResponse(BaseModel):
    success: bool
    stock_code: str
    stock_name: str
    updated_fields: list[str]
    message: str = ""


class StockProfileImportFileRequest(BaseModel):
    """批量导入请求：Base64 编码的 Excel/CSV 文件。"""

    content_base64: str = Field(min_length=1)
    filename: str = Field(default="profiles.xlsx", max_length=256)
    update_manual: bool = Field(
        default=False,
        description="是否覆盖手动维护(is_manual_override)的存量记录",
    )


class StockProfileImportResponse(BaseModel):
    total_rows: int
    added: int
    updated: int
    unchanged: int
    skipped: int
    invalid_rows: int
    warnings: list[str] = Field(default_factory=list)
