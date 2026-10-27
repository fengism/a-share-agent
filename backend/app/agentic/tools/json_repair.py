"""工具调用参数的 JSON 语法修复。

模型给出的参数经常是「几乎合法」的 JSON：套在 Markdown 代码围栏里、带尾逗号、
用单引号、写成 Python 字面量（``True``/``None``），或者被双重编码成字符串。
这些都不是语义错误，却会让工具白跑一轮、把配额浪费在「参数无效」上。

修复原则（重要）：

1. **只做语法层修复**，绝不猜测或补齐业务字段、绝不改数值；
2. 每一步修复后的结果都必须真正通过 ``json.loads`` 且是对象才被采用；
3. 无法修复时返回 ``None``，由调用方沿用既有约定把错误回给模型自我修正。

命中的修复规则会作为低基数指标上报（``tool_args_repaired:<rule>``），便于判断
某个模型的参数质量是否需要换模型或加提示词。
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

_FENCE_PATTERN = re.compile(r"^\s*```[A-Za-z0-9_+-]*[ \t]*\r?\n?(.*?)\r?\n?[ \t]*```\s*$", re.DOTALL)
_PY_LITERAL_PATTERN = re.compile(r"\b(True|False|None)\b")
_PY_LITERALS = {"True": "true", "False": "false", "None": "null"}


def strip_code_fence(text: str) -> str:
    """去掉整段的 Markdown 代码围栏（```json ... ```）。"""
    match = _FENCE_PATTERN.match(text)
    return match.group(1).strip() if match else text


def _map_outside_strings(text: str, transform: Callable[[str], str]) -> str:
    """只对字符串字面量之外的区段应用 transform，字符串内容原样保留。"""
    parts: list[str] = []
    start = 0
    index = 0
    while index < len(text):
        if text[index] != '"':
            index += 1
            continue
        parts.append(transform(text[start:index]))
        cursor = index + 1
        while cursor < len(text):
            if text[cursor] == "\\":
                cursor += 2
                continue
            if text[cursor] == '"':
                cursor += 1
                break
            cursor += 1
        parts.append(text[index:cursor])
        index = cursor
        start = cursor
    parts.append(transform(text[start:]))
    return "".join(parts)


def drop_trailing_commas(text: str) -> str:
    """删除 ``}``/``]`` 前的多余逗号（字符串感知，不会动到文本内容）。"""
    out: list[str] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character == '"':
            cursor = index + 1
            while cursor < len(text):
                if text[cursor] == "\\":
                    cursor += 2
                    continue
                if text[cursor] == '"':
                    cursor += 1
                    break
                cursor += 1
            out.append(text[index:cursor])
            index = cursor
            continue
        if character == ",":
            lookahead = index + 1
            while lookahead < len(text) and text[lookahead] in " \t\r\n":
                lookahead += 1
            if lookahead < len(text) and text[lookahead] in "}]":
                index += 1  # 丢弃这个逗号
                continue
        out.append(character)
        index += 1
    return "".join(out)


def convert_single_quotes(text: str) -> str:
    """把单引号 JSON 换成双引号。

    仅当文本里完全没有双引号时才动手：否则无法区分"字符串定界符"与"字符串内的
    撇号"，静默替换会把取值改坏。
    """
    if '"' in text or "'" not in text:
        return text
    return text.replace("'", '"')


def convert_python_literals(text: str) -> str:
    """把字符串外的 ``True``/``False``/``None`` 换成 JSON 字面量。"""
    return _map_outside_strings(
        text,
        lambda segment: _PY_LITERAL_PATTERN.sub(lambda match: _PY_LITERALS[match.group(1)], segment),
    )


def _try_load(text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None, None
    if isinstance(value, str):
        # 双重编码：网关把 arguments 当普通字符串又 JSON 序列化了一层。
        try:
            inner = json.loads(value)
        except json.JSONDecodeError:
            return None, None
        return (inner, "double_encoded") if isinstance(inner, dict) else (None, None)
    return (value, None) if isinstance(value, dict) else (None, None)


def load_arguments(raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    """解析工具参数，必要时做语法修复。

    Returns:
        ``(参数对象, 命中的修复规则)``；无法修复时返回 ``(None, None)``。
    """
    if isinstance(raw, dict):
        return raw, None
    text = "" if raw is None else str(raw).strip()
    if not text:
        # 无参工具常被模型写成空字符串；按空对象处理而不是报错。
        return {}, "empty"

    parsed, rule = _try_load(text)
    if parsed is not None:
        return parsed, rule

    # 修复按步骤链组合：每步都基于"已去围栏"的文本，标签记录真正生效的步骤，
    # 便于从指标上看出是哪个模型的哪种坏习惯。
    fenced = strip_code_fence(text)
    fence_parts: list[str] = ["fence"] if fenced != text else []

    variants: list[tuple[list[str], str]] = []
    if fence_parts:
        variants.append((fence_parts, fenced))

    no_trailing_comma = drop_trailing_commas(fenced)
    if no_trailing_comma != fenced:
        variants.append(([*fence_parts, "trailing_comma"], no_trailing_comma))

    quoted = convert_single_quotes(fenced)
    if quoted != fenced:
        variants.append(([*fence_parts, "single_quotes"], quoted))
        quoted_comma = drop_trailing_commas(quoted)
        if quoted_comma != quoted:
            variants.append(([*fence_parts, "single_quotes", "trailing_comma"], quoted_comma))

    literals = convert_python_literals(fenced)
    if literals != fenced:
        literal_parts = [*fence_parts, "python_literals"]
        literal_comma = drop_trailing_commas(literals)
        if literal_comma != literals:
            literal_parts.append("trailing_comma")
        variants.append((literal_parts, literal_comma))

    for parts, candidate in variants:
        parsed, extra_rule = _try_load(candidate)
        if parsed is None:
            continue
        return parsed, "+".join([*parts, extra_rule] if extra_rule else parts)
    return None, None
