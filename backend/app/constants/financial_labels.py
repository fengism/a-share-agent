"""
财务指标字段名 → 中文标签映射常量。
从 financial_labels.json 加载，保持向后兼容。
"""

import json
import os

_path = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_path, "financial_labels.json"), "r", encoding="utf-8") as _f:
    _data = json.load(_f)

FINANCIAL_RAW_FIELD_LABELS = _data["FINANCIAL_RAW_FIELD_LABELS"]
FINANCIAL_METRIC_ALIASES = _data["FINANCIAL_METRIC_ALIASES"]
FINANCIAL_METRIC_LABELS = _data["FINANCIAL_METRIC_LABELS"]
