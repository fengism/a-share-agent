CLS_MARKET_SECTOR_SOURCE_ID = "cls_market_sector_rankings"
CLS_MARKET_SECTOR_API = "https://x-quote.cls.cn/web_quote/plate/plate_list"
BAIDU_MARKET_SECTOR_SOURCE_ID = "baidu_market_sector_rankings"
BAIDU_MARKET_SECTOR_API = "https://finance.pae.baidu.com/vapi/v2/blocks"
EASTMONEY_MARKET_SECTOR_SOURCE_ID = "eastmoney_market_sector_rankings"
EASTMONEY_MARKET_SECTOR_API = "https://push2.eastmoney.com/api/qt/clist/get"
TENCENT_MARKET_SECTOR_SOURCE_ID = "tencent_market_sector_rankings"
TENCENT_MARKET_SECTOR_API = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/mktHs/rank"

CLS_MARKET_DISTRIBUTION_SOURCE_ID = "cls_market_pct_distribution"
CLS_MARKET_DISTRIBUTION_API = "https://x-quote.cls.cn/v2/quote/a/stock/emotion"
EASTMONEY_MARKET_DISTRIBUTION_SOURCE_ID = "eastmoney_market_pct_distribution"
EASTMONEY_MARKET_DISTRIBUTION_API = "https://push2ex.eastmoney.com/getTopicZDFenBu"

KAIPANHONG_LIMIT_UP_SOURCE_ID = "kaipanhong_limit_up_pool"
KAIPANHONG_LIMIT_UP_API = (
    "https://apphwshhq.kaipanhong.com/w1/api/index.php | "
    "https://apphis.kaipanhong.com/w1/api/index.php"
)
EASTMONEY_LIMIT_UP_SOURCE_ID = "eastmoney_limit_up_pool"
EASTMONEY_LIMIT_UP_API = "https://push2ex.eastmoney.com/getTopicZTPool"

EASTMONEY_LIMIT_DOWN_SOURCE_ID = "eastmoney_limit_down_pool"
EASTMONEY_LIMIT_DOWN_API = "https://push2ex.eastmoney.com/getTopicDTPool"

MARKET_STATISTICS_SOURCE_IDS = {
    "sector_rankings": TENCENT_MARKET_SECTOR_SOURCE_ID,
    "pct_distribution": EASTMONEY_MARKET_DISTRIBUTION_SOURCE_ID,
    "limit_up_pool": EASTMONEY_LIMIT_UP_SOURCE_ID,
    "limit_down_pool": EASTMONEY_LIMIT_DOWN_SOURCE_ID,
}

MARKET_STATISTICS_SOURCE_APIS = {
    CLS_MARKET_SECTOR_SOURCE_ID: CLS_MARKET_SECTOR_API,
    BAIDU_MARKET_SECTOR_SOURCE_ID: BAIDU_MARKET_SECTOR_API,
    EASTMONEY_MARKET_SECTOR_SOURCE_ID: EASTMONEY_MARKET_SECTOR_API,
    TENCENT_MARKET_SECTOR_SOURCE_ID: TENCENT_MARKET_SECTOR_API,
    CLS_MARKET_DISTRIBUTION_SOURCE_ID: CLS_MARKET_DISTRIBUTION_API,
    EASTMONEY_MARKET_DISTRIBUTION_SOURCE_ID: EASTMONEY_MARKET_DISTRIBUTION_API,
    KAIPANHONG_LIMIT_UP_SOURCE_ID: KAIPANHONG_LIMIT_UP_API,
    EASTMONEY_LIMIT_UP_SOURCE_ID: EASTMONEY_LIMIT_UP_API,
    EASTMONEY_LIMIT_DOWN_SOURCE_ID: EASTMONEY_LIMIT_DOWN_API,
}

INDEX_KLINE_SOURCE_APIS = {
    "东方财富指数K线直连": "https://push2his.eastmoney.com/api/qt/stock/kline/get",
    "TDX 指数K线": "mootdx://index",
    "Akshare 腾讯指数K线": "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
    "Akshare 东方财富指数K线": "https://push2his.eastmoney.com/api/qt/stock/kline/get",
    "Akshare 新浪指数K线": "https://finance.sina.com.cn/realstock/company/{symbol}/hisdata/klc_kl.js",
}
