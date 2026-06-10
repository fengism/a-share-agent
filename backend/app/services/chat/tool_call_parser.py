from __future__ import annotations

import json
import re

from app.models.chat import ToolCallFunction, ToolCallInfo
from app.services.chat.tools.registry import ChatRegistry


def _find_matching_paren(text: str, start: int) -> int:
    """在文本中从 start 位置开始查找匹配的右括号位置。

    Param:
        text: 待搜索的文本
        start: 起始位置（应指向左括号）
    Return:
        匹配的右括号索引，未找到返回 -1
    """
    depth = 0
    in_str = None
    i = start
    while i < len(text):
        c = text[i]
        if in_str:
            if c == "\\" and i + 1 < len(text):
                i += 2
                continue
            if c == in_str:
                in_str = None
        else:
            if c in ('"', "'"):
                in_str = c
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _parse_positional_args(args_text: str, param_order: list[str]) -> dict | None:
    """解析伪工具调用的参数文本，支持 JSON、位置参数和裸字符串三种格式。

    Param:
        args_text: 参数字符串
        param_order: 参数名称顺序列表
    Return:
        解析后的参数字典，解析失败返回 None
    """
    args_text = args_text.strip()
    if not args_text:
        return {}

    try:
        parsed = json.loads(args_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    try:
        parsed = json.loads(f"[{args_text}]")
        if isinstance(parsed, list):
            return {
                param_order[i]: value
                for i, value in enumerate(parsed)
                if i < len(param_order)
            }
    except json.JSONDecodeError:
        pass

    stripped = args_text.strip()
    if (stripped.startswith('"') and stripped.endswith('"')) or (
        stripped.startswith("'") and stripped.endswith("'")
    ):
        stripped = stripped[1:-1]
    return {param_order[0]: stripped} if param_order else None


def extract_pseudo_tool_calls(text: str, registry: ChatRegistry) -> list[ToolCallInfo]:
    """从 LLM 输出的纯文本中提取伪工具调用。

    某些模型不通过标准的 function calling 通道，而是直接在文本中写出 skill_name(args) 形式的调用。

    Param:
        text: LLM 输出的文本
        registry: 技能注册中心，用于查找 skill 定义和参数顺序
    Return:
        提取出的 ToolCallInfo 列表，每个对应一个伪工具调用
    """
    if not text:
        return []

    tools = registry.list_tools()
    names = [re.escape(t.name) for t in tools]
    if not names:
        return []

    pattern = re.compile(r"\b(" + "|".join(names) + r")\s*\(")
    calls: list[ToolCallInfo] = []

    for match in pattern.finditer(text):
        name = match.group(1)
        paren_start = match.end() - 1
        paren_end = _find_matching_paren(text, paren_start)
        if paren_end == -1:
            continue

        tool = registry.get_tool(name)
        if tool is None:
            continue

        param_order = list(tool.parameters.get("properties", {}).keys())
        args_dict = _parse_positional_args(text[paren_start + 1:paren_end], param_order)
        if args_dict is None:
            continue

        calls.append(ToolCallInfo(
            id=f"pseudo_{len(calls)}",
            type="function",
            function=ToolCallFunction(
                name=name,
                arguments=json.dumps(args_dict, ensure_ascii=False),
            ),
        ))

    return calls
