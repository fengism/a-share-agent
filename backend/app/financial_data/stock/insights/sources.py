BAIDU_FUND_FLOW_SOURCE_ID = "baidu_stock_fund_flow_history"
BAIDU_FUND_FLOW_API = "https://finance.pae.baidu.com/vapi/v1/fundsortlist"

EASTMONEY_FUND_FLOW_SOURCE_ID = "eastmoney_stock_fund_flow"
EASTMONEY_FUND_FLOW_API = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"

# 分笔成交金额分档估算，与百度/东方财富口径不等价。
TDXHUB_FUND_FLOW_SOURCE_ID = "tdxhub_stock_fund_flow_estimate"
TDXHUB_FUND_FLOW_API = "tdxhub.capital_flow"

EASTMONEY_MARGIN_TRADING_SOURCE_ID = "eastmoney_margin_trading"
EASTMONEY_BLOCK_TRADE_SOURCE_ID = "eastmoney_block_trade"
EASTMONEY_HOLDER_CHANGE_SOURCE_ID = "eastmoney_holder_num_change"
EASTMONEY_DATACENTER_API = "https://datacenter-web.eastmoney.com/api/data/v1/get"

RISK_FIELD_SOURCES = {
    "fund_flow": EASTMONEY_FUND_FLOW_SOURCE_ID,
    "margin_trading": EASTMONEY_MARGIN_TRADING_SOURCE_ID,
    "block_trade": EASTMONEY_BLOCK_TRADE_SOURCE_ID,
    "holder_change": EASTMONEY_HOLDER_CHANGE_SOURCE_ID,
}

RISK_SOURCE_APIS = {
    "fund_flow": EASTMONEY_FUND_FLOW_API,
    "margin_trading": f"{EASTMONEY_DATACENTER_API}?reportName=RPTA_WEB_RZRQ_GGMX",
    "block_trade": f"{EASTMONEY_DATACENTER_API}?reportName=RPT_DATA_BLOCKTRADE",
    "holder_change": f"{EASTMONEY_DATACENTER_API}?reportName=RPT_HOLDERNUMLATEST",
}

AKSHARE_EASTMONEY_HOT_SOURCE_ID = "akshare_eastmoney_stock_hot_detail"
AKSHARE_EASTMONEY_HOT_API = (
    "https://emappdata.eastmoney.com/stockrank/getHisList | "
    "https://emappdata.eastmoney.com/stockrank/getHisProfileList"
)
STOCK_NEWS_AGGREGATE_SOURCE_ID = "stock_news_aggregate"
STOCK_NEWS_AGGREGATE_API = "/api/stock/{code}/news"
EASTMONEY_GUBA_SOURCE_ID = "eastmoney_guba_posts"
EASTMONEY_GUBA_API = "http://guba.eastmoney.com/list,{code},f_{page}.html"
SINA_BULLETIN_SOURCE_ID = "sina_stock_bulletins"
SINA_BULLETIN_LIST_API = "CB_AllService.getBulletinList"
SINA_REPORT_SOURCE_ID = "sina_stock_reports"
SINA_REPORT_LIST_API = "ReportService.getList"
