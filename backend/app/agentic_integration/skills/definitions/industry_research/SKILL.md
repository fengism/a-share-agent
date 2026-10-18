---
name: industry_research
description: 行业、板块、题材、大宗商品现货与海关出海数据研究
triggers:
- 行业、板块或题材分析
- 行业热度、成分股或相关研报
- 大宗商品与工业品现货价格
- 海关进出口与出海产业链量价数据
activation_keywords:
- 行业
- 板块
- 题材
- 产业链
- 大宗商品
- 现货价格
- 出海
- 海关
- 出口
- 进口
- 汽车出海
- 锂电出海
- 光伏出海
tools:
- sector_analysis
- get_hot_rank
- iwencai_search
- get_commodity_spot_prices
- get_customs_trade_data
priority: 50
exclusions:
- 单一问题不要同时调用综合分析和其组成工具
examples:
- 分析光伏产业链上下游格局 ➔ sector_analysis('光伏')
- 查看汽车与新能源出海最新海关出口数据 ➔ get_customs_trade_data('汽车')
- 查看碳酸锂与工业硅最新现货价格 ➔ get_commodity_spot_prices('碳酸锂')
- 查看当前热门行业与概念排名 ➔ get_hot_rank(type='industries')
---

## Rules

- 行业或产业链综合分析用 sector_analysis；仅看热度排名用 get_hot_rank。
- 大宗商品及重要工业品现货/期货价格用 get_commodity_spot_prices。
- 海关月度进出口总况及重点商品（汽车、锂电、光伏、芯片、家电、机械）出海数据用 get_customs_trade_data。
- 仅查研报、公告或新闻时用 iwencai_search。
