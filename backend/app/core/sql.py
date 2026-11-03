"""SQL 相关的共享小工具。

目前只包含 ``LIKE`` 模式转义：把用户输入拼进 ``LIKE`` 模式时，``%`` 与 ``_`` 必须
当成字面量，否则搜索 ``%`` 会命中全表、搜索 ``_`` 会匹配任意单字符，结果与用户
预期完全不符（虽然参数化已经挡住了注入）。

用法：SQL 里写 ``LIKE ? ESCAPE '\\'``，参数用 :func:`contains_pattern` /
:func:`prefix_pattern` 构造。反斜杠在 SQLite 字符串字面量中不是特殊字符，所以
``ESCAPE`` 子句可以固定写死，不需要拼接 SQL。
"""

from __future__ import annotations

#: 转义符。必须与 SQL 里 ``ESCAPE '\'`` 子句使用的字符一致。
LIKE_ESCAPE_CHAR = "\\"


def escape_like(value: str) -> str:
    """转义 ``LIKE`` 模式中的通配符，使其按字面量匹配。

    Param:
        value: 用户输入关键词。
    Return:
        转义后的字符串；配合 SQL 中的 ``ESCAPE '\\'`` 使用。
    """
    escaped = value.replace(LIKE_ESCAPE_CHAR, LIKE_ESCAPE_CHAR * 2)
    return escaped.replace("%", f"{LIKE_ESCAPE_CHAR}%").replace("_", f"{LIKE_ESCAPE_CHAR}_")


def contains_pattern(value: str) -> str:
    """构造「包含」语义的 ``LIKE`` 模式（两侧通配符 + 已转义的字面量）。"""
    return f"%{escape_like(value)}%"


def prefix_pattern(value: str) -> str:
    """构造「前缀」语义的 ``LIKE`` 模式（右侧通配符 + 已转义的字面量）。"""
    return f"{escape_like(value)}%"
