---
name: url_content
description: 网页与 PDF 研报阅读与对比
triggers:
- 消息包含 HTTP(S) 链接或 PDF 文档
- 阅读、总结或对比网页/PDF内容
activation_keywords:
- 阅读
- 总结
- 网页内容
- 对比网页
- pdf
- 研报正文
- 公告原文
tools:
- web_fetch
- fetch_urls
- read_pdf
priority: 10
exclusions:
- 不要自动联动股票工具，除非用户明确要求结合行情分析
examples: []
---

## Rules

- 单个链接用 web_fetch；多个链接一次性用 fetch_urls；PDF 研报/公告使用 read_pdf 读取指定页码与表格。
- 默认使用 mode=auto；明确需要 JS 渲染时用 dynamic，普通 HTTP 被反爬拦截时用 stealth。
- 仅依据抓取正文作答；抓取失败时说明原因，不补写原文没有的信息。
