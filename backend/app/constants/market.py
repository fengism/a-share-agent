INDEX_FALLBACKS = [
    ("000001", "上证指数", "1.000001"),
    ("399001", "深证成指", "0.399001"),
    ("399006", "创业板指", "0.399006"),
    ("000688", "科创50", "1.000688"),
    ("000300", "沪深300", "1.000300"),
    ("000905", "中证500", "1.000905"),
]

SINA_INDEX_QUOTE_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeDataSimple"
SINA_INDEX_PAGE_COUNT_URL = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeStockCountSimple?node=hs_s"
)
SINA_MARKET_HQ_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
SINA_STOCK_KLINE_URL = "https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData"

EASTMONEY_STOCK_KLINE_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_CLIST_URL = "http://push2.eastmoney.com/api/qt/clist/get"

EASTMONEY_SEARCH_SUGGEST_URL = "https://searchapi.eastmoney.com/api/suggest/get"
EASTMONEY_SEARCH_SUGGEST_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"
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

A_SHARE_SEARCH_CLASSIFY = {"AStock", "Ashares", "AStockSH", "AStockSZ", "AStockBJ"}
