"""跨领域共享的宽松数值解析。

数据源（第三方 JSON、行情接口、爬取的表格）返回的「数字」经常带千分位逗号、
空串、``None`` 或非有限浮点数。历史上多个 provider 各自实现了一份同名的私有
``_safe_float`` / ``_number``，行为略有出入。这里统一为两个语义明确的函数。

区分：
- :func:`parse_float` —— 宽松解析，容许 ``"1,234.5"`` 这类带分隔符的文本。
- :func:`coerce_finite_float` —— 直接 ``float()``，并过滤 ``nan`` / ``inf``。
"""

from __future__ import annotations

import math
from typing import Any

__all__ = ["coerce_finite_float", "parse_float"]


def parse_float(value: Any) -> float | None:
    """把可能带千分位逗号的文本解析为浮点数，失败返回 ``None``。

    Param:
        value: 任意待解析值（``None`` / 空串 / ``"1,234.5"`` / ``12.3``）
    Return:
        解析成功且为有限数时返回 ``float``，否则返回 ``None``
    """
    if value is None:
        return None
    try:
        text = str(value).replace(",", "").strip()
        if not text:
            return None
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def coerce_finite_float(value: Any) -> float | None:
    """把值转成有限的浮点数，``None`` / 空串 / ``nan`` / ``inf`` 一律返回 ``None``。

    不做逗号清理，适用于已经是数值或标准数字文本的场景。

    Param:
        value: 任意待解析值
    Return:
        有限浮点数或 ``None``
    """
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None
