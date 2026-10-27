"""CSV 导出安全工具：阻断电子表格公式注入（CSV injection）。

Excel / WPS / Numbers 打开 CSV 时，会把以 ``=``、``+``、``-``、``@``（以及前置
制表符、回车）开头的单元格当**公式**求值。本仓库的导出字段里包含同步任务与
管理员可写的半可信文本（公司简称、概念名、一级/二级行业、主营业务等），
一旦有人写入 ``=cmd|'/c calc'!A1`` 这类内容，下载导出文件的人就会被执行。

防护方式与 OWASP 建议一致：给可疑单元格加单引号前缀，让表格软件按文本处理。
纯数字（含负数、科学计数法）保持原样，避免把数值列变成文本影响筛选排序。
"""

from __future__ import annotations

from collections.abc import Iterable

#: 会让表格软件进入公式求值模式的首字符。
_FORMULA_PREFIXES: frozenset[str] = frozenset({"=", "+", "-", "@", "\t", "\r", "\n"})

#: 需要先剥掉再判断的空白/控制字符（部分表格软件会忽略前导空白）。
_LEADING_NOISE: frozenset[str] = frozenset({" ", "\t", "\r", "\n", "\x00", "\ufeff"})


def _looks_like_plain_number(text: str) -> bool:
    """``-1.5`` / ``+3.2e5`` 这类纯数字不需要转义，其余 ``-`` 开头一律视为可疑。"""
    try:
        float(text)
    except (TypeError, ValueError):
        return False
    return True


def csv_safe_cell(value: object) -> str:
    """把单元格值转成安全的 CSV 文本（None → 空串，其余转 str 后按需加引号前缀）。"""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if not text:
        return text
    # 找到第一个非噪声字符，判断是否会触发公式
    index = 0
    while index < len(text) and text[index] in _LEADING_NOISE:
        index += 1
    if index >= len(text):
        return text
    if text[index] not in _FORMULA_PREFIXES:
        return text
    if _looks_like_plain_number(text.strip()):
        return text
    return "'" + text


def csv_safe_row(values: Iterable[object]) -> list[str]:
    """逐列转义，供 ``csv.writer.writerow`` 使用。"""
    return [csv_safe_cell(value) for value in values]
