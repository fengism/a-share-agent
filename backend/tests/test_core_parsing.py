"""跨领域共享的解析/转义辅助（app.core.parsing / html / dataframes）契约。

这些函数是从各模块的同名私有实现收敛而来，行为必须与原先一致，因此用参数化
用例把边界（空串、千分位、NaN、Infinity、None、缺失值）锁死。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core.dataframes import clean_cell_text
from app.core.html import escape_html
from app.core.parsing import coerce_finite_float, parse_float


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1,234.5", 1234.5),
        ("-1,000", -1000.0),
        (" 12.5 ", 12.5),
        ("0", 0.0),
        (12.5, 12.5),
        ("", None),
        ("   ", None),
        (None, None),
        ("abc", None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
        # 逗号一律删除后再解析，与收敛前的私有实现保持一致
        ("1,2,3", 123.0),
        ("1.2.3", None),
    ],
)
def test_parse_float(value: object, expected: float | None) -> None:
    assert parse_float(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (12.5, 12.5),
        ("12.5", 12.5),
        (0, 0.0),
        ("", None),
        (None, None),
        ("abc", None),
        (float("nan"), None),
        (float("inf"), None),
        # 与 parse_float 的区别：不做千分位清理
        ("1,234.5", None),
    ],
)
def test_coerce_finite_float(value: object, expected: float | None) -> None:
    assert coerce_finite_float(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;"),
        ('a "b" \'c\'', "a &quot;b&quot; &#x27;c&#x27;"),
        ("A&B", "A&amp;B"),
        ("", ""),
        (None, ""),
        (123, "123"),
        # 中文与非 ASCII 原样保留
        ("贵州茅台", "贵州茅台"),
    ],
)
def test_escape_html(value: object, expected: str) -> None:
    assert escape_html(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  贵州茅台  ", "贵州茅台"),
        ("", ""),
        (None, ""),
        (float("nan"), ""),
        (pd.NaT, ""),
        (pd.NA, ""),
        (np.nan, ""),
    ],
)
def test_clean_cell_text(value: object, expected: str) -> None:
    assert clean_cell_text(value) == expected


def test_escape_html_roundtrip_via_stdlib() -> None:
    """确保转义不会二次转义已转义的实体以外的东西。"""
    assert escape_html("&amp;") == "&amp;amp;"
