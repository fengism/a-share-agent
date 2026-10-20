---
name: financial_calculations
description: 常用财务固定公式（无需 Python 服务）
triggers:
- 收益率或复合增长率计算
- 现金流折现与财务比率
- 波动率和最大回撤
activation_keywords:
- 计算
- 测算
- 收益率
- cagr
- 复合增长率
- npv
- 净现值
- dcf
- 折现
- 贴现
- 波动率
- 最大回撤
- 财务比率
tools:
- financial_calculator
priority: 39
exclusions: []
examples: []
---

## Rules

- 常用计算优先 financial_calculator；必须核实现金流时间、年化频率和单位，百分数转换为小数。
- 参数错误必须修正输入，不得自动转 Python 绕过；不猜测缺失的数据和假设。
- 返回时展示公式和关键假设；固定工具无需 Python 服务，普通用户也可使用。
