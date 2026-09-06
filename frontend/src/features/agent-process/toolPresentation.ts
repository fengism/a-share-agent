const TOOL_LABELS: Record<string, string> = {
  analyze_financials: "财务分析",
  fetch_url: "网页正文",
  fetch_urls: "批量网页正文",
  get_commodity_spot_prices: "大宗商品现货价",
  get_customs_trade_data: "海关进出口与出海数据",
  get_global_macro_rates: "全球宏观利率与汇率",
  get_interactive_qa: "董秘互动问答",
  get_market_overview: "市场概览",
  get_restricted_shares_lift: "限售解禁监控",
  get_stock_info: "股票资料",
  get_stock_kline: "K 线行情",
  get_stock_news: "公司新闻",
  get_stock_risk_data: "风险数据",
  get_stock_sentiment: "市场情绪",
  get_stock_technical_indicators: "技术指标",
  get_stock_valuation_detail: "估值分析",
  iwencai_query: "问财结构化查询",
  iwencai_search: "问财搜索",
  public_industry_data: "产业公共数据",
  python_interpreter: "Python 计算沙盒",
  read_pdf: "阅读 PDF 研报/公告",
  web_search: "网页搜索",
};

export function toolDisplayName(name: string): string {
  return TOOL_LABELS[name] || name;
}
