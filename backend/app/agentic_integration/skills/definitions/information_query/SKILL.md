---
name: information_query
description: 公开网页、资讯检索与自然语言结构化查询
triggers:
- 搜索互联网或查找公开网页
- 查找研报、公告或新闻
- 无法映射为固定工具参数的数据查询
activation_keywords:
- 搜索
- 查找
- 检索
- 网页
- 白皮书
- 公开来源
- 资料来源
- pdf
tools:
- web_search
- web_fetch
- fetch_urls
- read_pdf
- iwencai_search
- iwencai_query
priority: 70
exclusions:
- 选股问题使用 iwencai_select_stock 或 screen_stocks
examples: []
---

## Rules

- 公开互联网网页和通用资料先用 web_search；搜索结果只用于发现候选页面，不视为完整正文。
- 今日或最新资讯将 time_range 设为 day，近期动态设为 week，普通检索默认 half_year；仅历史或静态资料使用 any。
- 默认使用中文关键词并设置 language=zh；仅在中文资料不足时补充英文权威来源。
- 用户需要详细内容时，必须对 web_search 返回的 URL 调用 web_fetch；需要阅读多个结果时调用 fetch_urls。
- 研报、公告或财经新闻优先用 iwencai_search；非选股的结构化数据问题用 iwencai_query。
