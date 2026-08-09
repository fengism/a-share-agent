from __future__ import annotations

import json
import re
from collections.abc import Collection

from app.agentic.catalog import CapabilityCatalog
from app.agentic.protocol import ToolCallFunction, ToolCallInfo


def build_assistant_tool_message(
    tool_calls: list[ToolCallInfo],
    content: str | None = None,
) -> dict:
    return {
        "role": "assistant",
        "content": content or None,
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in tool_calls
        ],
    }


def tool_call_infos_from_stream(
    tool_calls_accumulator: dict[int, dict[str, str]],
) -> list[ToolCallInfo]:
    return [
        ToolCallInfo(
            id=tool_call_data["id"] or f"call_{index}",
            type="function",
            function=ToolCallFunction(
                name=tool_call_data["name"],
                arguments=tool_call_data["arguments"],
            ),
        )
        for index, tool_call_data in sorted(tool_calls_accumulator.items())
    ]


def _find_matching_parenthesis(text: str, start: int) -> int:
    depth = 0
    quote: str | None = None
    index = start
    while index < len(text):
        character = text[index]
        if quote:
            if character == "\\" and index + 1 < len(text):
                index += 2
                continue
            if character == quote:
                quote = None
        elif character in ('"', "'"):
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _parse_arguments(arguments: str, parameter_order: list[str]) -> dict | None:
    arguments = arguments.strip()
    if not arguments:
        return {}

    try:
        parsed = json.loads(arguments)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    try:
        parsed = json.loads(f"[{arguments}]")
        if isinstance(parsed, list):
            return {
                parameter_order[index]: value
                for index, value in enumerate(parsed)
                if index < len(parameter_order)
            }
    except json.JSONDecodeError:
        pass

    stripped = arguments.strip()
    if (stripped.startswith('"') and stripped.endswith('"')) or (
        stripped.startswith("'") and stripped.endswith("'")
    ):
        stripped = stripped[1:-1]
    return {parameter_order[0]: stripped} if parameter_order else None


def extract_pseudo_tool_calls(
    text: str,
    catalog: CapabilityCatalog,
    allowed_names: Collection[str] | None = None,
) -> list[ToolCallInfo]:
    if not text:
        return []

    tools = [
        tool
        for tool in catalog.list_tools()
        if allowed_names is None or tool.name in allowed_names
    ]
    names = [re.escape(tool.name) for tool in tools]
    if not names:
        return []

    pattern = re.compile(r"\b(" + "|".join(names) + r")\s*\(")
    calls: list[ToolCallInfo] = []
    for match in pattern.finditer(text):
        name = match.group(1)
        parenthesis_start = match.end() - 1
        parenthesis_end = _find_matching_parenthesis(text, parenthesis_start)
        if parenthesis_end == -1:
            continue

        tool = catalog.get_tool(name)
        if tool is None:
            continue
        parameter_order = list(tool.parameters.get("properties", {}).keys())
        arguments = _parse_arguments(
            text[parenthesis_start + 1:parenthesis_end],
            parameter_order,
        )
        if arguments is None:
            continue
        calls.append(
            ToolCallInfo(
                id=f"pseudo_{len(calls)}",
                type="function",
                function=ToolCallFunction(
                    name=name,
                    arguments=json.dumps(arguments, ensure_ascii=False),
                ),
            )
        )
    return calls
