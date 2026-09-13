"""股票基础资料的数据来源目录。"""

from collections.abc import Callable
from dataclasses import dataclass

from app.constants.market import (
    BAIDU_STOCK_NAMES_URL,
    EASTMONEY_CLIST_URL,
    EASTMONEY_STOCK_PROFILE_URL,
    SINA_MARKET_HQ_URL,
    TENCENT_STOCK_CONCEPT_URL,
    TENCENT_STOCK_QUOTE_URL,
)
from app.financial_data.stock.profile.name_sources import (
    BAIDU_STOCK_NAMES_SOURCE_ID,
    BSE_STOCK_NAMES_SOURCE_ID,
    CNINFO_STOCK_NAMES_SOURCE_ID,
    EASTMONEY_STOCK_NAMES_SOURCE_ID,
    LEGACY_STOCK_NAMES_SOURCE_ID,
    SINA_STOCK_NAMES_SOURCE_ID,
    SSE_STOCK_NAMES_SOURCE_ID,
    SZSE_STOCK_NAMES_SOURCE_ID,
    TDXHUB_STOCK_NAMES_SOURCE_ID,
)
from app.financial_data.stock.profile.schemas import StockDataSource
from app.financial_data.stock.quotes.sources import (
    AKSHARE_SPOT_SOURCE_ID,
    EASTMONEY_SPOT_SOURCE_ID,
    LEGACY_SPOT_SOURCE_ID,
    SINA_CN_RANK_SPOT_SOURCE_ID,
    SINA_SPOT_SOURCE_ID,
)


@dataclass(frozen=True)
class BasicDataSourceSpec:
    """基础资料上游来源定义。"""

    id: str
    name: str
    provider: str
    operation: str
    api: str | Callable[[], str]

    def to_contract(self) -> StockDataSource:
        return StockDataSource(
            id=self.id,
            name=self.name,
            provider=self.provider,
            operation=self.operation,
            api=self.api() if callable(self.api) else self.api,
        )


EASTMONEY_STOCK_PROFILE = BasicDataSourceSpec(
    id="eastmoney.stock_profile",
    name="东方财富个股资料",
    provider="eastmoney",
    operation="stock_basic_info",
    api=EASTMONEY_STOCK_PROFILE_URL,
)
SSE_STOCK_LISTING = BasicDataSourceSpec(
    id=SSE_STOCK_NAMES_SOURCE_ID,
    name="上交所证券名录",
    provider="exchange",
    operation="stock_names_sh",
    api="https://query.sse.com.cn/sseQuery/commonQuery.do",
)
SZSE_STOCK_LISTING = BasicDataSourceSpec(
    id=SZSE_STOCK_NAMES_SOURCE_ID,
    name="深交所证券名录",
    provider="exchange",
    operation="stock_names_sz",
    api=(
        "https://www.szse.cn/api/report/ShowReport?SHOWTYPE=xlsx&CATALOGID=1110&TABKEY=tab1 | "
        "https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1110&TABKEY=tab1"
    ),
)
BSE_STOCK_LISTING = BasicDataSourceSpec(
    id=BSE_STOCK_NAMES_SOURCE_ID,
    name="北交所证券名录",
    provider="exchange",
    operation="stock_names_bj",
    api="https://www.bse.cn/nqxxController/nqxxCnzq.do",
)
TENCENT_STOCK_QUOTE = BasicDataSourceSpec(
    id="tencent.stock_quote",
    name="腾讯实时行情",
    provider="tencent",
    operation="stock_quote",
    api=f"{TENCENT_STOCK_QUOTE_URL}{{symbols}}",
)
TENCENT_STOCK_CONCEPTS = BasicDataSourceSpec(
    id="tencent.stock_concepts",
    name="腾讯行业概念",
    provider="tencent",
    operation="stock_concepts",
    api=TENCENT_STOCK_CONCEPT_URL,
)
SINA_SPOT_SNAPSHOT = BasicDataSourceSpec(
    id=SINA_SPOT_SOURCE_ID,
    name="新浪全市场行情快照",
    provider="sina",
    operation="spot_snapshot",
    api=SINA_MARKET_HQ_URL,
)
SINA_CN_RANK_SPOT_SNAPSHOT = BasicDataSourceSpec(
    id=SINA_CN_RANK_SPOT_SOURCE_ID,
    name="新浪全市场排行快照",
    provider="sina",
    operation="spot_snapshot_cnrank",
    api="https://cnrank.finance.sina.cn/getSymRankByNode",
)
EASTMONEY_SPOT_SNAPSHOT = BasicDataSourceSpec(
    id=EASTMONEY_SPOT_SOURCE_ID,
    name="东方财富全市场行情快照",
    provider="eastmoney",
    operation="spot_snapshot",
    api=EASTMONEY_CLIST_URL,
)
AKSHARE_SPOT_SNAPSHOT = BasicDataSourceSpec(
    id=AKSHARE_SPOT_SOURCE_ID,
    name="AkShare 东方财富行情快照",
    provider="akshare",
    operation="spot_snapshot",
    api="akshare.stock_zh_a_spot_em",
)
LEGACY_SPOT_SNAPSHOT = BasicDataSourceSpec(
    id=LEGACY_SPOT_SOURCE_ID,
    name="旧版本地行情快照",
    provider="local-cache",
    operation="spot_snapshot",
    api="stock_spot_snapshot.json (upstream unavailable)",
)
CNINFO_STOCK_NAMES = BasicDataSourceSpec(
    id=CNINFO_STOCK_NAMES_SOURCE_ID,
    name="巨潮资讯股票名称列表",
    provider="cninfo",
    operation="stock_names",
    api="https://www.cninfo.com.cn/new/data/szse_stock.json",
)
BAIDU_STOCK_NAMES = BasicDataSourceSpec(
    id=BAIDU_STOCK_NAMES_SOURCE_ID,
    name="百度股票名称列表",
    provider="baidu",
    operation="stock_names",
    api=BAIDU_STOCK_NAMES_URL,
)
EASTMONEY_STOCK_NAMES = BasicDataSourceSpec(
    id=EASTMONEY_STOCK_NAMES_SOURCE_ID,
    name="东方财富股票名称列表",
    provider="eastmoney",
    operation="stock_names",
    api=EASTMONEY_CLIST_URL,
)
SINA_STOCK_NAMES = BasicDataSourceSpec(
    id=SINA_STOCK_NAMES_SOURCE_ID,
    name="新浪股票名称列表",
    provider="sina",
    operation="stock_names",
    api=SINA_MARKET_HQ_URL,
)
TDXHUB_STOCK_NAMES = BasicDataSourceSpec(
    id=TDXHUB_STOCK_NAMES_SOURCE_ID,
    name="TDX 股票名称列表",
    provider="tdxhub",
    operation="stock_names",
    api="tdxhub.Quotes.stock_all(security_type='a_stock')",
)
TDXHUB_STOCK_QUOTE = BasicDataSourceSpec(
    id="tdxhub.stock_quote",
    name="TDX 实时行情",
    provider="tdxhub",
    operation="stock_quote",
    api="tdxhub.Quotes.quotes(codes)",
)
TDXHUB_FINANCE = BasicDataSourceSpec(
    id="tdxhub.finance",
    name="TDX 财务基础信息",
    provider="tdxhub",
    operation="finance",
    api="tdxhub.Quotes.finance(code)",
)
LEGACY_STOCK_NAMES = BasicDataSourceSpec(
    id=LEGACY_STOCK_NAMES_SOURCE_ID,
    name="旧版股票名称缓存",
    provider="local-cache",
    operation="stock_names",
    api="stock_names.json (upstream unavailable)",
)
SW_INDUSTRY_CLASSIFICATION = BasicDataSourceSpec(
    id="sw_industry",
    name="申万行业分类",
    provider="industry_data.db",
    operation="sw_industry_classification",
    api="sw_industry_classifications",
)
STOCK_CONCEPT_MAPPING = BasicDataSourceSpec(
    id="stock_concept",
    name="个股概念库",
    provider="industry_data.db",
    operation="stock_concept_mapping",
    api="stock_concept_mappings",
)

_SOURCE_CATALOG = {
    source.id: source
    for source in (
        EASTMONEY_STOCK_PROFILE,
        SSE_STOCK_LISTING,
        SZSE_STOCK_LISTING,
        BSE_STOCK_LISTING,
        TENCENT_STOCK_QUOTE,
        TENCENT_STOCK_CONCEPTS,
        SW_INDUSTRY_CLASSIFICATION,
        STOCK_CONCEPT_MAPPING,
        SINA_SPOT_SNAPSHOT,
        SINA_CN_RANK_SPOT_SNAPSHOT,
        EASTMONEY_SPOT_SNAPSHOT,
        AKSHARE_SPOT_SNAPSHOT,
        LEGACY_SPOT_SNAPSHOT,
        BAIDU_STOCK_NAMES,
        EASTMONEY_STOCK_NAMES,
        SINA_STOCK_NAMES,
        TDXHUB_STOCK_NAMES,
        TDXHUB_STOCK_QUOTE,
        TDXHUB_FINANCE,
        LEGACY_STOCK_NAMES,
    )
}
_EXCHANGE_SOURCES = {
    "SH": SSE_STOCK_LISTING,
    "SZ": SZSE_STOCK_LISTING,
    "BJ": BSE_STOCK_LISTING,
}


def exchange_listing_source(exchange: str) -> BasicDataSourceSpec:
    return _EXCHANGE_SOURCES[exchange]


def source_contracts(source_ids: list[str]) -> list[StockDataSource]:
    """按首次出现顺序返回去重后的来源契约。"""
    return [_SOURCE_CATALOG[source_id].to_contract() for source_id in dict.fromkeys(source_ids)]
