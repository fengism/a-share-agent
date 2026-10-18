---
name: stock_analysis
description: 个股识别、查询与分析（支持A股与港股）
triggers:
- 股票名称、6位A股代码或1-5位港股代码
- 个股估值、技术面、财报、港股行情走势、风险或多股对比
activation_keywords:
- 股票
- 个股
- 股价
- 估值
- 市盈率
- 市净率
- pe
- pb
- 财报
- 财务
- roe
- 营收
- 净利润
- 主营构成
- 产品构成
- 业务构成
- 地区构成
- 毛利构成
- k线
- macd
- rsi
- kdj
- 技术面
- 基本面
- 新闻
- 公告
- 舆情
- 情绪
- 风险
- 止损
- 仓位
- 目标价
- 支撑位
- 压力位
- 走势
- 港股
- 恒指
- 恒生
- 港元
- h股
tools:
- search_stocks
- get_stock_info
- get_stock_valuation_detail
- get_stock_technical_indicators
- get_stock_kline
- get_stock_financial
- get_stock_documents
- get_stock_news
- get_stock_sentiment
- get_stock_risk_data
- get_restricted_shares_lift
- get_interactive_qa
- analyze_stock
- analyze_financials
- compare_stocks
- get_hk_stock_profile
- get_hk_stock_kline
- get_hk_stock_technical_indicators
- get_hk_stock_industry_comparison
priority: 30
exclusions:
- 调用组合工具后不要重复调用其组成工具
- 已确认代码后不要再次搜索
examples:
- 查询茅台最新估值与财报 ➔ get_stock_valuation_detail('600519')
- 对比宁德时代与比亚迪 ➔ compare_stocks(['300750', '002594'])
- 分析平安银行技术指标 ➔ get_stock_technical_indicators('000001')
- 分析腾讯控股港股行情与走势 ➔ get_hk_stock_profile('00700') 与 get_hk_stock_kline('00700')
- 查看网易在港股同行业的竞争地位与对手估值 ➔ get_hk_stock_industry_comparison('09999')
---

## Rules

- 完整6位A股代码直接使用A股工具；港股（1-5位代码如00700、09988或明确为港股）使用 get_hk_stock_profile、get_hk_stock_kline、get_hk_stock_technical_indicators、get_hk_stock_industry_comparison；切勿对港股调用A股专用的 analyze_stock/analyze_financials/get_stock_info。
- 仅有名称或代码不完整时先调用一次 search_stocks。
- A股全面分析用 analyze_stock；完整财报分析用 analyze_financials；多股横向比较用 compare_stocks；港股行业竞争对手对比用 get_hk_stock_industry_comparison。
- 仅问单一维度时调用对应单项工具，不升级为全面分析。
