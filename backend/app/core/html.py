"""HTML 转义辅助。

三个报表渲染器（个股分析 / 产业链 / 每日复盘）以及图表内嵌 SVG 都需要把外部
文本转义后嵌入 HTML。历史上各自写了一份 ``_esc``，其中一份只转义 ``&``/``<``/``>``，
遗漏了引号。这里统一使用 :func:`html.escape` 的完整语义（``quote=True``）。
"""

from __future__ import annotations

import html
from typing import Any

__all__ = ["escape_html"]


def escape_html(value: Any) -> str:
    """把任意值转成可安全嵌入 HTML 文本的字符串。

    ``None`` 映射为空串；``&``/``<``/``>``/``"``/``'`` 全部转义。

    Param:
        value: 任意待转义值
    Return:
        转义后的字符串
    """
    if value is None:
        return ""
    return html.escape(str(value))
