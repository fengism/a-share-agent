"""东方财富新闻内容清洗。

pandas 3 的字符串 dtype 底层是 pyarrow，其正则引擎（RE2）不接受 ``\\uXXXX``
转义：``Series.str.replace(r"\\u3000", regex=True)`` 会抛
``ArrowInvalid: Invalid regular expression: invalid escape sequence: \\u``，
导致整个个股新闻接口失败。因此全角空格/换行必须走 regex=False 的字面量替换。
"""

import pandas as pd

from app.infrastructure.providers.eastmoney.news import _strip_em_tags


def test_strip_em_tags_removes_highlight_markup() -> None:
    series = pd.Series(["<em>贵州</em>茅台", "无标记"])
    assert _strip_em_tags(series).tolist() == ["贵州茅台", "无标记"]


def test_content_cleanup_uses_literal_replacement() -> None:
    """回归：全角空格与换行用字面量替换，避开 pyarrow 正则的 \\u 转义限制。"""
    series = pd.Series(["标题\u3000内容\r\n第二行", "正常内容"])
    cleaned = series.str.replace("\u3000", "", regex=False).str.replace("\r\n", " ", regex=False)
    assert cleaned.tolist() == ["标题内容 第二行", "正常内容"]