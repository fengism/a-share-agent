---
name: twitter_account
description: Twitter/X 账号观点分析
triggers:
- 明确要求分析某个 Twitter/X 用户或财经账号
activation_keywords:
- twitter 账号
- twitter账号
- x 账号
- x账号
- 推特账号
tools:
- analyze_twitter_user
priority: 20
exclusions:
- 普通推文链接使用 web_fetch，不要启动账号级分析
examples: []
---

## Rules

- 调用 analyze_twitter_user，仅传用户名且不含 @；基于工具结果作答。
