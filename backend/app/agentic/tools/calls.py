from __future__ import annotations

import json
import re
from collections.abc import Collection
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.agentic.catalog import CapabilityCatalog, registry
from app.agentic.protocol import ToolCallFunction, ToolCallInfo
from app.agentic.runtime.metrics import metrics
from app.agentic.tools.json_repair import load_arguments
from app.agentic.tools.validation import ToolArgumentsError, coerce_arguments

# Model echoes the wire-format argument name into the payload body. Only unwrap
# when the key is not a real schema property.
_WIRE_ENVELOPE_KEYS = ("arguments", "parameters", "input", "args")


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


@dataclass(frozen=True, slots=True)
class PreparedToolCall:
    """A normalized call plus parsed/coerced arguments for one execution."""

    call: ToolCallInfo
    arguments: Any | None


def _rewrite_arguments(tool_call: ToolCallInfo, arguments: Any) -> ToolCallInfo:
    """把解析/修复后的参数写回调用，保证回放历史、缓存键和 Tool.execute 看到同一份 JSON。"""
    return tool_call.model_copy(update={
        "function": ToolCallFunction(
            name=tool_call.function.name,
            arguments=json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
        )
    })


def prepare_tool_call(tool_call: ToolCallInfo) -> PreparedToolCall:
    """Parse and validate arguments once; ``None`` defers error reporting to Tool.execute.

    解析前会做一次**纯语法**修复（代码围栏/尾逗号/单引号/Python 字面量/双重编码），
    命中的规则计入指标；无法修复时保持原样，仍由 Tool.execute 报参数错误。
    """
    tool = registry.get_tool(tool_call.function.name)
    if tool is None:
        return PreparedToolCall(tool_call, None)
    parsed, repair_rule = load_arguments(tool_call.function.arguments)
    if parsed is None:
        return PreparedToolCall(tool_call, None)
    if repair_rule is not None:
        metrics.record_agentic_event(f"tool_args_repaired:{repair_rule}")
        tool_call = _rewrite_arguments(tool_call, parsed)
    try:
        coerced = coerce_arguments(parsed, tool.parameters)
    except ToolArgumentsError:
        # 语法已修好：保留修好的 arguments，让 Tool.execute 的兜底路径至少能解析，
        # 错误信息也能指向真正的 schema 不符，而不是"JSON 解析失败"。
        return PreparedToolCall(tool_call, None)
    if coerced is parsed:
        return PreparedToolCall(tool_call, parsed)
    return PreparedToolCall(_rewrite_arguments(tool_call, coerced), coerced)


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

    # 正文方言里的参数同样常带尾逗号/单引号：先走统一的语法修复，再退回位置参数
    # 与单值启发式（修复器只接受对象，非对象形态自然落到下面的分支）。
    repaired, _rule = load_arguments(arguments)
    if repaired is not None:
        return repaired

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


@lru_cache(maxsize=64)
def _cached_tool_name_pattern(names: tuple[str, ...]) -> re.Pattern[str]:
    """Compile the pseudo-call matcher once per stable tool-name tuple."""
    return re.compile(r"\b(" + "|".join(re.escape(name) for name in names) + r")\s*\(")


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
    names = tuple(tool.name for tool in tools)
    if not names:
        return []

    pattern = _cached_tool_name_pattern(names)
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

    if calls:
        return calls
    # `tool_name(...)` 之外，模型还会把调用写成标记正文（DeepSeek DSML 等）。认不出来
    # 的方言会漏成回答正文，所以这里必须同样尝试一遍。
    return extract_markup_tool_calls(text, catalog, allowed_names)


# ── 正文形态的工具调用标记 ──────────────────────────────────────────────
# 模型会把工具调用写成正文而不是结构化 tool_calls。真实事故：用户在 chat 里收到的
# 「回答」是一串
#   <｜DSML｜tool_calls><｜DSML｜invoke name="analyze_financials">…
# 因为 extract_pseudo_tool_calls 只认 `tool_name(...)`，标记既没被执行、也没被拦下，
# 直接被当成最终结论流给用户。这里做两件事：认出来（转成真实调用）、兜底擦掉
# （任何方言都不允许出现在回答里）。
_BAR = r"[|｜]"
_DSML_TAG = r"<\s*" + _BAR + r"\s*DSML\s*" + _BAR + r"\s*"
_QUOTED_NAME = r"(?P<quote>[\"']?)(?P<name>[A-Za-z0-9_.\-]+)(?P=quote)"

_DSML_INVOKE = re.compile(
    _DSML_TAG + r"invoke\s+name\s*=\s*" + _QUOTED_NAME + r"[^>]*>(?P<body>.*?)"
    r"<\s*/\s*" + _BAR + r"\s*DSML\s*" + _BAR + r"\s*invoke\s*>",
    re.DOTALL,
)
_DSML_PARAMETER = re.compile(
    _DSML_TAG + r"parameter\s+name\s*=\s*" + _QUOTED_NAME + r"[^>]*>(?P<value>.*?)"
    r"<\s*/\s*" + _BAR + r"\s*DSML\s*" + _BAR + r"\s*parameter\s*>",
    re.DOTALL,
)
_TAGGED_JSON_BLOCK = re.compile(
    r"<\s*(?P<tag>tool_calls?|function_calls?)\s*>(?P<body>.*?)<\s*/\s*(?P=tag)\s*>",
    re.DOTALL | re.IGNORECASE,
)
_TAGGED_JSON_OPEN = re.compile(r"<\s*(?:tool_calls?|function_calls?)\s*>", re.IGNORECASE)
_TOOL_CALLS_MARKER = "[TOOL_CALLS]"

# 标记块边界：开标签用于进入「抑制」状态，闭标签用于恢复。两处都覆盖全角/半角竖线。
# 开标签必须匹配到完整的开标签（带右尖括号 `>`），以保证提取出准确完整的 tag 名称，
# 从而配对正确的闭标签（例如 `<｜DSML｜tool_calls>` 配对 `</｜DSML｜tool_calls>`）。
# 未写完的开标签由 `_partial_opener_start` 暂存在 `_pending` 中等待下一块。
_MARKUP_OPEN = re.compile(
    r"<\s*" + _BAR + r"\s*DSML\s*" + _BAR + r"\s*(?P<tag>tool_calls?|invoke|parameter)\b[^>]*>"
    r"|<\s*(?P<tag2>tool_calls?|function_calls?)\s*>"
    r"|(?P<marker>" + re.escape(_TOOL_CALLS_MARKER) + r")",
    re.IGNORECASE,
)
_MARKUP_CLOSE = re.compile(
    r"<\s*/\s*(?:(?:" + _BAR + r"\s*DSML\s*" + _BAR + r")|(?=tool_calls?|function_calls?|invoke))"
    r"(?:tool_calls?|function_calls?|invoke)\s*>",
    re.IGNORECASE,
)


def _closer_for(match: re.Match[str]) -> re.Pattern[str] | None:
    """由开标签推出配对的闭标签；``[TOOL_CALLS]`` 没有闭标签。"""
    tag = match.group("tag") or match.group("tag2")
    if tag is None:
        return None
    escaped = re.escape(tag)
    if match.group("tag"):
        return re.compile(
            r"<\s*/\s*" + _BAR + r"\s*DSML\s*" + _BAR + r"\s*" + escaped + r"\s*>",
            re.IGNORECASE,
        )
    return re.compile(r"<\s*/\s*" + escaped + r"\s*>", re.IGNORECASE)


def _parameter_value(raw: str) -> Any:
    """参数值优先按 JSON 解析，解析不了就当字符串（模型会漏引号）。"""
    text = raw.strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _inline_arguments(body: str) -> dict[str, Any] | None:
    text = body.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _dsml_invoke_arguments(body: str) -> dict[str, Any] | None:
    parameters: dict[str, Any] = {}
    for match in _DSML_PARAMETER.finditer(body):
        parameters[match.group("name")] = _parameter_value(match.group("value"))
    return parameters or _inline_arguments(body)


def _json_entry_arguments(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    name = entry.get("name") or entry.get("tool")
    if not isinstance(name, str) or not name:
        return None
    raw = entry.get("arguments", entry.get("parameters", entry.get("input")))
    if isinstance(raw, str):
        parsed = _inline_arguments(raw)
        arguments = parsed if parsed is not None else {"value": raw}
    elif isinstance(raw, dict):
        arguments = raw
    else:
        arguments = {}
    return {"name": name, "arguments": arguments}


def _json_tool_entries(body: str) -> list[dict[str, Any]]:
    text = body.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # 只取第一个完整 JSON 值，后面的噪声（多余说明）不该毁掉整次解析。
        try:
            parsed, _ = json.JSONDecoder().raw_decode(text)
        except json.JSONDecodeError:
            return []
    candidates = parsed if isinstance(parsed, list) else [parsed]
    return [entry for entry in (_json_entry_arguments(item) for item in candidates) if entry]


def _unwrap_wire_envelope(
    arguments: dict[str, Any], catalog: CapabilityCatalog, name: str
) -> dict[str, Any]:
    """拆掉模型回显的一层线格式参数外壳（``{"arguments": {...}}``）。

    线格式的参数名就是 ``arguments``，模型会把它一起写进调用里。``coerce_arguments``
    只在「原样校验报的是缺少必填参数」时才拆，没有必填参数的 schema 永远轮不到它，
    于是同一工具每次都稳定报「包含未声明参数：arguments」。这里按同样的边界拆：
    只认单键包装、内层是对象，且该键没有被 schema 声明。
    """
    if len(arguments) != 1:
        return arguments
    key, inner = next(iter(arguments.items()))
    if key not in _WIRE_ENVELOPE_KEYS or not isinstance(inner, dict):
        return arguments
    tool = catalog.get_tool(name)
    if tool is None or key in (tool.parameters.get("properties") or {}):
        return arguments
    return inner


def _build_pseudo_calls(entries: list[dict[str, Any]]) -> list[ToolCallInfo]:
    return [
        ToolCallInfo(
            id=f"markup_{index}",
            type="function",
            function=ToolCallFunction(
                name=entry["name"],
                arguments=json.dumps(entry["arguments"], ensure_ascii=False),
            ),
        )
        for index, entry in enumerate(entries)
    ]


def extract_markup_tool_calls(
    text: str,
    catalog: CapabilityCatalog,
    allowed_names: Collection[str] | None = None,
) -> list[ToolCallInfo]:
    """把写成正文的工具调用标记还原成真实调用。

    认不出来的方言必须由 ``strip_tool_call_markup`` 兜底擦掉：标记要么被执行，
    要么被移除，绝不允许作为回答内容出现在用户面前。
    """
    if not text:
        return []

    def usable(name: str) -> bool:
        if allowed_names is not None and name not in allowed_names:
            return False
        return catalog.get_tool(name) is not None

    entries: list[dict[str, Any]] = []
    for match in _DSML_INVOKE.finditer(text):
        name = match.group("name")
        if not usable(name):
            continue
        arguments = _dsml_invoke_arguments(match.group("body"))
        if arguments is None:
            continue
        entries.append({"name": name, "arguments": _unwrap_wire_envelope(arguments, catalog, name)})
    if entries:
        return _build_pseudo_calls(entries)

    for match in _TAGGED_JSON_BLOCK.finditer(text):
        entries.extend(
            _normalized_entry(entry, catalog)
            for entry in _json_tool_entries(match.group("body"))
            if usable(entry["name"])
        )
    marker_index = text.find(_TOOL_CALLS_MARKER)
    if marker_index != -1:
        entries.extend(
            _normalized_entry(entry, catalog)
            for entry in _json_tool_entries(text[marker_index + len(_TOOL_CALLS_MARKER):])
            if usable(entry["name"])
        )
    return _build_pseudo_calls(entries)


def _normalized_entry(entry: dict[str, Any], catalog: CapabilityCatalog) -> dict[str, Any]:
    """按工具 schema 拆掉 JSON 方言里回显的线格式参数外壳。"""
    return {
        "name": entry["name"],
        "arguments": _unwrap_wire_envelope(entry["arguments"], catalog, entry["name"]),
    }


def has_tool_call_markup(text: str) -> bool:
    """正文里是否残留工具调用标记（含未闭合的截断残片）。"""
    if not text:
        return False
    return bool(
        _MARKUP_OPEN.search(text) or _DSML_PARAMETER.search(text) or _MARKUP_CLOSE.search(text)
    )


_DSML_CONTAINER_BLOCK = re.compile(
    _DSML_TAG + r"tool_calls?\s*>.*?<\s*/\s*" + _BAR + r"\s*DSML\s*" + _BAR + r"\s*tool_calls?\s*>",
    re.DOTALL,
)
_DSML_INVOKE_BLOCK = re.compile(
    _DSML_TAG + r"invoke\b.*?<\s*/\s*" + _BAR + r"\s*DSML\s*" + _BAR + r"\s*invoke\s*>",
    re.DOTALL,
)
_DSML_UNCLOSED = re.compile(
    _DSML_TAG + r"(?:tool_calls?|invoke|parameter)\b.*\Z", re.DOTALL
)
_DSML_LEFTOVER_TAG = re.compile(
    r"<\s*/?\s*" + _BAR + r"\s*DSML\s*" + _BAR + r"[^>]*>", re.DOTALL
)
_TAGGED_JSON_CLOSE = re.compile(r"<\s*/\s*(?:tool_calls?|function_calls?)\s*>", re.IGNORECASE)


def _strip_tool_calls_marker(text: str) -> str:
    """移除 ``[TOOL_CALLS]`` 标记及其紧随的 JSON 载荷。"""
    index = text.find(_TOOL_CALLS_MARKER)
    if index == -1:
        return text
    tail = text[index + len(_TOOL_CALLS_MARKER):].lstrip()
    try:
        _, end = json.JSONDecoder().raw_decode(tail)
    except json.JSONDecodeError:
        return text[:index]
    consumed = len(text[index + len(_TOOL_CALLS_MARKER):]) - len(tail) + end
    return text[:index] + text[index + len(_TOOL_CALLS_MARKER) + consumed:]


def strip_tool_call_markup(text: str) -> str:
    """移除正文里的工具调用标记，只保留可读的分析文字。

    闭合块整段删除；未闭合（模型被截断）时删到末尾——半截标记比没有输出更糟：
    既不可读，又会让人误以为拿到了结论。
    """
    if not text or not has_tool_call_markup(text):
        return text

    cleaned = _DSML_CONTAINER_BLOCK.sub("", text)
    cleaned = _DSML_INVOKE_BLOCK.sub("", cleaned)
    cleaned = _DSML_UNCLOSED.sub("", cleaned)
    cleaned = _TAGGED_JSON_BLOCK.sub("", cleaned)
    cleaned = _TAGGED_JSON_OPEN.sub("", cleaned)
    cleaned = _TAGGED_JSON_CLOSE.sub("", cleaned)
    cleaned = _strip_tool_calls_marker(cleaned)
    # 兜底：任何残余的 DSML 标签本身就是标记，不可能属于正文
    cleaned = _DSML_LEFTOVER_TAG.sub("", cleaned)
    return cleaned.strip()


class ToolCallMarkupStreamFilter:
    """逐块过滤流式正文里的工具调用标记。

    只在正文边生成边推送（``tool_choice="none"`` 的最终轮）时使用：标记一旦进入流就
    无法撤回，必须在推给用户之前拦下。跨块拆开的开/闭标签会被暂存，合并后再判定；
    正常正文必须照旧逐块推出去（缓冲到流末尾等于取消流式）。
    """

    _MAX_TAIL = 32

    def __init__(self) -> None:
        self._pending = ""
        self._closer: re.Pattern[str] | None = None
        self._suppressing = False

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._pending += chunk
        emitted: list[str] = []
        while True:
            if self._suppressing and not self._consume_closer():
                return "".join(emitted)
            match = _MARKUP_OPEN.search(self._pending)
            if match is None:
                break
            emitted.append(self._pending[: match.start()])
            self._pending = self._pending[match.end():]
            self._closer = _closer_for(match)
            self._suppressing = True
        if not self._suppressing:
            tail_start = self._partial_opener_start()
            if tail_start < 0:
                emitted.append(self._pending)
                self._pending = ""
            elif tail_start > 0:
                emitted.append(self._pending[:tail_start])
                self._pending = self._pending[tail_start:]
        return "".join(emitted)

    def flush(self) -> str:
        pending, self._pending = self._pending, ""
        if self._suppressing:
            # 标记始终没有闭合：整段丢弃，交给「空回答」的既有处理。
            self._suppressing = False
            self._closer = None
            return ""
        return strip_tool_call_markup(pending)

    def _consume_closer(self) -> bool:
        if self._closer is None:
            # [TOOL_CALLS] 没有闭合标记：只能吞到流末尾。
            self._pending = self._pending[-self._MAX_TAIL:]
            return False
        match = self._closer.search(self._pending)
        if match is None:
            # 结尾可能是被切开的闭合标签，留一小段尾部等下一块。
            self._pending = self._pending[-self._MAX_TAIL:]
            return False
        self._pending = self._pending[match.end():]
        self._suppressing = False
        self._closer = None
        return True

    def _partial_opener_start(self) -> int:
        """返回结尾处「可能是半个开标签」的起点，避免标记被切成两半后漏出去。"""
        candidate = re.search(r"<[^<>]{0,80}$|\[[A-Z_]{0,12}$", self._pending)
        return candidate.start() if candidate is not None else -1
