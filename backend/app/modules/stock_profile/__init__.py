"""个股基础资料库模块。

提供个股基础信息（代码、名称、上市板块、上市时间、主营业务、经营范围、主要产品等）
的持久化存储、维护、查询与同步能力。
"""

from app.modules.stock_profile.public import (
    StockBasicProfileInput,
    StockBasicProfileListResponse,
    StockBasicProfileRecord,
    StockBasicProfileSummary,
    StockProfileEnrichResponse,
    enrich_stock_profile,
    get_profile,
    get_profile_summary,
    get_stock_profile_record,
    list_profiles,
    list_stock_profile_records,
    remove_profile,
    save_profile,
    sync_exchange_master_data,
)

__all__ = [
    "StockBasicProfileInput",
    "StockBasicProfileRecord",
    "StockBasicProfileListResponse",
    "StockBasicProfileSummary",
    "StockProfileEnrichResponse",
    "list_profiles",
    "get_profile",
    "save_profile",
    "remove_profile",
    "get_profile_summary",
    "enrich_stock_profile",
    "sync_exchange_master_data",
    "get_stock_profile_record",
    "list_stock_profile_records",
]
