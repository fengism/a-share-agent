INDEX_FALLBACKS = [
    ("000001", "上证指数", "1.000001"),
    ("399001", "深证成指", "0.399001"),
    ("399006", "创业板指", "0.399006"),
    ("000688", "科创50", "1.000688"),
    ("000300", "沪深300", "1.000300"),
    ("000905", "中证500", "1.000905"),
]

SINA_INDEX_QUOTE_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple"
SINA_INDEX_INTRADAY_URL = "https://cn.finance.sina.com.cn/minline/getMinlineData"
SINA_MARKET_HQ_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
SINA_MARKET_HQ_COUNT_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCount"
SINA_MARKET_NODES_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes"
SINA_CN_RANK_URL = "https://cnrank.finance.sina.cn/getSymRankByNode"
SINA_STOCK_KLINE_URL = "https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData"
SINA_BULLETIN_LIST_URL = "https://vip.stock.finance.sina.com.cn/corp/api/openapi.php/CB_AllService.getBulletinList"
SINA_REPORT_LIST_URL = "https://stock.finance.sina.com.cn/stock/api/openapi.php/ReportService.getList"

EASTMONEY_STOCK_KLINE_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_CLIST_URL = "http://push2.eastmoney.com/api/qt/clist/get"
EASTMONEY_STOCK_PROFILE_URL = "https://push2.eastmoney.com/api/qt/stock/get"

# 东方财富 push2 节点池（包含原始主节点及常见镜像节点）
EASTMONEY_PUSH2_NODES = [
    "push2.eastmoney.com",
    "17.push2.eastmoney.com",
    "45.push2.eastmoney.com",
    "79.push2.eastmoney.com",
    "82.push2.eastmoney.com",
    "98.push2.eastmoney.com",
    "100.push2.eastmoney.com",
]


def get_random_push2_host() -> str:
    """从东财 push2 节点池（包含原始主节点与 6 个镜像节点）中随机选取一个节点。"""
    import random

    return random.choice(EASTMONEY_PUSH2_NODES)


TENCENT_STOCK_CONCEPT_URL = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/stockinfo/plateNew"
TENCENT_STOCK_QUOTE_URL = "https://qt.gtimg.cn/q="
BAIDU_STOCK_NAMES_URL = "https://finance.pae.baidu.com/selfselect/getmarketrank"

# 东财证券代码表搜索接口。老的 searchapi suggest 接口已改为 JSONP 包裹
# （jQuery…({...})）且返回论坛用户而非证券代码，response.json() 必然 JSONDecodeError。
EASTMONEY_SEARCH_URL = "https://search-codetable.eastmoney.com/codetable/search"
# codetable 的板块标签：A 股只有沪/深/京主板与科创板（创业板归在深A、北交所归在京A）。
# 其余（指数/板块/债券/基金/LOF/B股/港美股/退市）都不是「股票」——注意 000001
# 上证指数与 000001 平安银行代码完全相同，只能靠标签区分。
EASTMONEY_A_SHARE_LABELS = frozenset({"沪A", "深A", "京A", "科创"})
EASTMONEY_API_TOKEN = "fa5fd1943c7b386f172d6893dbfba10b"
EASTMONEY_UT_TOKEN = "b2884a393a59ad64002292a3e90d46a5"
EASTMONEY_UT_TOKEN_ALT = "8dec03ba335b81bf4ebdf7b29ec27d15"
EASTMONEY_UT_TRADE = "bd1d9ddb04089700cf9c27f6f7426281"
EASTMONEY_UT_HISTORY = "7eea3edcaed734bea9cbfc24409ed989"
EASTMONEY_INVESTOR_TYPE = "2"
EASTMONEY_FLATTEN_FLAG = "1"
EASTMONEY_KLINE_FIELDS1 = "f1,f2,f3,f4,f5,f6"
EASTMONEY_KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
EASTMONEY_INDEX_QUOTE_FIELDS = "f1,f2,f3,f4,f5,f6,f7,f10,f12,f13,f14,f15,f16,f17,f18,f152"
