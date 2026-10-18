---
name: python_code_interpreter
description: 财务固定公式优先；未覆盖的自定义分析使用隔离 Python（仅管理员）
triggers:
- 复杂数值计算
- CAGR 复合增长率测算
- 现金流折现 DCF 计算
- 敏感性分析与统计测算
activation_keywords:
- 计算
- 测算
- cagr
- 复合增长率
- dcf
- 贴现
- 折现
- 敏感性
- 方差
- 夏普比率
- python
- 收益率
- 波动率
- 最大回撤
- npv
- 净现值
- 财务比率
tools:
- financial_calculator
- python_interpreter
priority: 40
exclusions: []
examples:
- 测算2024到2030年规模从10亿到80亿的CAGR ➔ financial_calculator(operation='cagr', inputs={'start_value':10,'end_value':80,'years':6})
---

## Rules

- 收益率、CAGR、NPV、DCF、波动率、最大回撤和财务比率必须优先使用 financial_calculator；核实单位、期间和现金流口径。
- 固定公式参数错误时先修正输入，不得调用 Python 绕过；只有公式未覆盖的分析才使用 python_interpreter。
- Python 仅管理员可用，执行服务不可用时不回退本机执行；固定公式仍可独立使用。
- 代码中必须包含 print(...) 输出最终结果。
