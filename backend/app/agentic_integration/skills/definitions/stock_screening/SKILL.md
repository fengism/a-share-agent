---
name: stock_screening
description: 条件选股与固定维度筛选
triggers:
- 选股、筛选股票
- 市盈率、市净率、涨跌幅、行业等条件组合
activation_keywords:
- 选股
- 筛选
- 哪些股票
- 股票池
tools:
- iwencai_select_stock
- screen_stocks
- get_industries
priority: 40
exclusions:
- 不要用 iwencai_query 代替选股
- 同一条件不要同时调用两种选股工具
examples:
- 选出市盈率小于20且ROE大于15%的白酒股 ➔ iwencai_select_stock(query='市盈率<20，ROE>15%，白酒行业')
- 筛选半导体板块涨幅前十 ➔ screen_stocks(industries=['半导体'], sort_by='change_pct', sort_order='desc')
---

## Rules

- 自然语言或复杂条件优先用 iwencai_select_stock。
- 条件可精确映射到固定字段时才用 screen_stocks；行业名称不确定时先用 get_industries。
