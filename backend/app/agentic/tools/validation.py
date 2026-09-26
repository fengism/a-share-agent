"""Agentic Tool 参数 Schema 与执行器契约校验。"""

import inspect
import json
import math
import re
from datetime import date
from typing import Any
from urllib.parse import urlsplit

SUPPORTED_SCHEMA_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
# 只允许这些关键字：它们必须全部被 validate_value 真正实现，否则等于对模型撒谎。
SUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "type", "properties", "required", "additionalProperties", "default",
        "description", "enum", "const", "format", "items",
        "minItems", "maxItems", "uniqueItems",
        "minLength", "maxLength", "pattern",
        "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    }
)


class ToolArgumentsError(ValueError):
    """Tool arguments do not satisfy the declared JSON Schema.

    ``reason``/``field``/``detail`` 是给界面展示用的受控结构化信息，与 ``message``
    分开：message 会完整回给模型（含模型自己传入的键名，便于它自我纠正），而
    field/detail 只允许来自 schema 的键名与约束值——模型输入的键名必须先过标识符
    白名单，否则任意字符串都会被打到界面上。
    """

    def __init__(
        self,
        message: str,
        *,
        reason: str = "",
        field: str = "",
        detail: str = "",
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.field = field
        self.detail = detail


# 模型传入的键名是不受控输入，只有形如标识符的才允许出现在界面文案里。
_SAFE_ARGUMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
_MAX_REPORTED_UNEXPECTED_NAMES = 5


def _field_of(path: str) -> str:
    """把校验路径 ``参数.code``/``参数.codes[0]`` 转成界面可用的字段名。"""
    return path.removeprefix("参数").lstrip(".")


def _safe_names(names: list[str]) -> str:
    """过滤模型输入的键名，只保留合法标识符，超出数量上限的折叠成计数。"""
    safe = [name for name in names if _SAFE_ARGUMENT_NAME.fullmatch(name)]
    if not safe:
        return f"{len(names)} 个"
    shown = "、".join(safe[:_MAX_REPORTED_UNEXPECTED_NAMES])
    if len(safe) > _MAX_REPORTED_UNEXPECTED_NAMES:
        shown += f" 等 {len(safe)} 个"
    elif len(safe) < len(names):
        # 有键名因不是合法标识符被过滤掉了，仍要让人知道总数，否则会漏报。
        shown += f" 等 {len(names)} 个"
    return shown


# OpenAI/DeepSeek 风格的 tool_calls 里，参数本体挂在 arguments 字段下。部分模型会
# 把这个线格式字段名回显进参数体，发来 {"arguments": {"code": "600519"}} 而不是
# {"code": "600519"}。这里列出几种等价的外壳名，只在它们未被 schema 声明时才拆。
_ARGUMENT_ENVELOPE_KEYS = ("arguments", "parameters", "input", "args")
_MAX_ARGUMENT_ENVELOPE_DEPTH = 3


def _enveloped_payload(value: Any, schema: dict[str, Any]) -> dict[str, Any] | None:
    """若 value 是「单键为外壳名、值为对象」的包装，返回内层；否则 None。"""
    if not isinstance(value, dict) or len(value) != 1:
        return None
    name, inner = next(iter(value.items()))
    if name not in _ARGUMENT_ENVELOPE_KEYS or not isinstance(inner, dict):
        return None
    # 工具真的声明了同名参数，这不是外壳，不能拆。
    if name in schema.get("properties", {}):
        return None
    return inner


def matches_schema_type(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return False


def validate_value(value: Any, schema: dict[str, Any], path: str = "参数") -> None:
    expected = schema.get("type")
    expected_types = [expected] if isinstance(expected, str) else list(expected or [])
    if expected_types and not any(matches_schema_type(value, item) for item in expected_types):
        raise ToolArgumentsError(
            f"{path} 类型错误，应为 {'/'.join(expected_types)}",
            reason="type_mismatch",
            field=_field_of(path),
            detail=f"应为 {'/'.join(expected_types)}",
        )

    if "enum" in schema and value not in schema["enum"]:
        raise ToolArgumentsError(
            f"{path} 必须是 {schema['enum']} 之一",
            reason="enum",
            field=_field_of(path),
            detail=f"可选 {'、'.join(str(item) for item in schema['enum'])}",
        )

    if "const" in schema and value != schema["const"]:
        raise ToolArgumentsError(
            f"{path} 必须是 {schema['const']!r}",
            reason="const_mismatch",
            field=_field_of(path),
            detail=f"只能是 {schema['const']!r}",
        )

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        missing = [name for name in schema.get("required", []) if name not in value]
        if missing:
            # missing 来自 schema.required，本身就是受控字段名。
            raise ToolArgumentsError(
                f"缺少必填参数：{', '.join(missing)}",
                reason="missing_required",
                detail="、".join(missing),
            )
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                # extra 来自模型实际传入的键，必须过滤后才能出现在界面文案里。
                raise ToolArgumentsError(
                    f"包含未声明参数：{', '.join(extra)}",
                    reason="unexpected_parameter",
                    detail=_safe_names(extra),
                )
        for name, item in value.items():
            if property_schema := properties.get(name):
                validate_value(item, property_schema, f"{path}.{name}")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ToolArgumentsError(
                f"{path} 至少需要 {schema['minItems']} 项",
                reason="min_items",
                field=_field_of(path),
                detail=f"至少 {schema['minItems']} 项",
            )
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ToolArgumentsError(
                f"{path} 最多允许 {schema['maxItems']} 项",
                reason="max_items",
                field=_field_of(path),
                detail=f"最多 {schema['maxItems']} 项",
            )
        if schema.get("uniqueItems"):
            normalized = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(normalized) != len(set(normalized)):
                raise ToolArgumentsError(
                    f"{path} 不允许重复项",
                    reason="duplicate_items",
                    field=_field_of(path),
                )
        if item_schema := schema.get("items"):
            for index, item in enumerate(value):
                validate_value(item, item_schema, f"{path}[{index}]")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ToolArgumentsError(
                f"{path} 长度不能小于 {schema['minLength']}",
                reason="min_length",
                field=_field_of(path),
                detail=f"至少 {schema['minLength']} 字符",
            )
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ToolArgumentsError(
                f"{path} 长度不能超过 {schema['maxLength']}",
                reason="max_length",
                field=_field_of(path),
                detail=f"最多 {schema['maxLength']} 字符",
            )
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, value) is None:
            raise ToolArgumentsError(
                f"{path} 格式不正确",
                reason="pattern",
                field=_field_of(path),
            )
        if schema.get("format") == "date":
            try:
                date.fromisoformat(value)
            except ValueError as error:
                raise ToolArgumentsError(
                    f"{path} 必须是有效的 YYYY-MM-DD 日期",
                    reason="invalid_date",
                    field=_field_of(path),
                    detail="YYYY-MM-DD",
                ) from error
        if schema.get("format") == "uri":
            try:
                parsed = urlsplit(value)
                hostname = parsed.hostname
            except ValueError as error:
                raise ToolArgumentsError(
                    f"{path} 必须是有效的 HTTP(S) URL",
                    reason="invalid_url",
                    field=_field_of(path),
                ) from error
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or not hostname:
                raise ToolArgumentsError(
                    f"{path} 必须是有效的 HTTP(S) URL",
                    reason="invalid_url",
                    field=_field_of(path),
                )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            raise ToolArgumentsError(
                f"{path} 必须是有限数值",
                reason="not_finite",
                field=_field_of(path),
            )
        if "minimum" in schema and value < schema["minimum"]:
            raise ToolArgumentsError(
                f"{path} 不能小于 {schema['minimum']}",
                reason="below_minimum",
                field=_field_of(path),
                detail=f"不得小于 {schema['minimum']}",
            )
        if "maximum" in schema and value > schema["maximum"]:
            raise ToolArgumentsError(
                f"{path} 不能大于 {schema['maximum']}",
                reason="above_maximum",
                field=_field_of(path),
                detail=f"不得大于 {schema['maximum']}",
            )
        # exclusiveMinimum/Maximum 之前完全没有实现：schema 写了约束、模型看到的是
        # 合法区间，值落到 pydantic 才被拒，最终只得到一个不透明的 execution_failed。
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            raise ToolArgumentsError(
                f"{path} 必须大于 {schema['exclusiveMinimum']}",
                reason="below_exclusive_minimum",
                field=_field_of(path),
                detail=f"必须大于 {schema['exclusiveMinimum']}",
            )
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            raise ToolArgumentsError(
                f"{path} 必须小于 {schema['exclusiveMaximum']}",
                reason="above_exclusive_maximum",
                field=_field_of(path),
                detail=f"必须小于 {schema['exclusiveMaximum']}",
            )
        if (divisor := schema.get("multipleOf")) and divisor > 0:
            ratio = value / divisor
            if not math.isclose(ratio, round(ratio), rel_tol=1e-9, abs_tol=1e-9):
                raise ToolArgumentsError(
                    f"{path} 必须是 {divisor} 的整数倍",
                    reason="not_multiple_of",
                    field=_field_of(path),
                    detail=f"必须是 {divisor} 的整数倍",
                )


def coerce_arguments(parsed: Any, schema: dict[str, Any]) -> Any:
    """按 schema 校验参数，并在需要时拆掉模型多包的一层参数外壳。

    直接校验包装形态会命中「缺少必填参数」，而线格式一直在提示模型用 arguments
    这个名字，于是它稳定复现，表现为同一工具反复报「工具参数无效」。

    触发条件刻意收窄到「原样校验报的是缺少必填参数」：只有这种形状才符合
    「多包了一层外壳」这个假设。其它错误照实报出——比如模型把 parameters 当成
    某个工具的真实参数名传进来，那属于用错字段名，解包会把错误信号变成静默成功。

    外壳还必须是单键包装、且该键未被 schema 声明，因此不会误伤真正声明了同名
    参数的工具；原样合法时原样返回。
    """
    try:
        validate_value(parsed, schema)
        return parsed
    except ToolArgumentsError as error:
        if error.reason != "missing_required":
            raise
        inner = parsed
        for _ in range(_MAX_ARGUMENT_ENVELOPE_DEPTH):
            candidate = _enveloped_payload(inner, schema)
            if candidate is None:
                break
            inner = candidate
        if inner is parsed:
            raise
        validate_value(inner, schema)
        return inner


def validate_schema(schema: dict[str, Any], path: str = "parameters") -> None:
    if not isinstance(schema, dict):
        raise ValueError(f"{path} 必须是对象")
    unknown = sorted(set(schema) - SUPPORTED_SCHEMA_KEYWORDS)
    if unknown:
        # 白名单式校验：写了没实现的关键字等于没写。模型会以为约束生效（比如
        # exclusiveMinimum），值一路穿到 pydantic 才被拒，只得到一个不透明的
        # execution_failed —— 必须在注册期就失败。
        raise ValueError(f"{path} 使用了未实现的关键字：{unknown}")
    expected = schema.get("type")
    expected_types = [expected] if isinstance(expected, str) else list(expected or [])
    if not expected_types or any(item not in SUPPORTED_SCHEMA_TYPES for item in expected_types):
        raise ValueError(f"{path}.type 不合法")
    properties = schema.get("properties", {})
    if "object" in expected_types and not isinstance(properties, dict):
        raise ValueError(f"{path}.properties 必须是对象")
    required = schema.get("required", [])
    if not isinstance(required, list) or not set(required).issubset(properties):
        raise ValueError(f"{path}.required 包含未声明参数")
    for name, property_schema in properties.items():
        validate_schema(property_schema, f"{path}.properties.{name}")
        if "default" in property_schema:
            validate_value(property_schema["default"], property_schema, f"{path}.{name}.default")
    if "items" in schema:
        validate_schema(schema["items"], f"{path}.items")


def validate_executor_contract(tool: Any) -> None:
    if tool.executor is None:
        raise ValueError(f"工具 '{tool.name}' 缺少 executor")
    if not inspect.iscoroutinefunction(tool.executor):
        raise ValueError(f"工具 '{tool.name}' 的 executor 必须是异步函数")
    parameters = inspect.signature(tool.executor).parameters
    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )
    schema_properties = tool.parameters.get("properties", {})
    unsupported = [
        name for name in schema_properties if name not in parameters and not accepts_kwargs
    ]
    if unsupported:
        raise ValueError(f"工具 '{tool.name}' 的 Schema 参数未被 executor 接收：{unsupported}")

    required = set(tool.parameters.get("required", []))
    required_parameter_kinds = {
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    }
    missing = [
        name
        for name, parameter in parameters.items()
        if parameter.kind in required_parameter_kinds
        and parameter.default is inspect.Parameter.empty
        and name not in required
    ]
    if missing:
        raise ValueError(
            f"工具 '{tool.name}' 的 executor 必填参数未在 Schema required 声明：{missing}"
        )

    # 反向校验：executor 能接收的参数必须全部声明在 Schema 里，否则模型永远传不进去，
    # 只会静默退回默认值。screen_stocks 的 page/page_size 就是这样漏的——下游在翻页、
    # 返回体也带 page，Schema 却没声明，模型一传就被 additionalProperties 拒绝。
    #
    # 位置-only 与 *args 同样要拒：Tool.execute 一律用 executor(**arguments) 调用，
    # 位置-only 参数根本传不进去（注册期能过、运行时必 TypeError）；*args 则让
    # 反向校验看不到任何参数，作用等同于 **kwargs。
    if accepts_kwargs:
        raise ValueError(
            f"工具 '{tool.name}' 的 executor 使用 **kwargs，Schema 无法与执行器互相校验；"
            "请在 executor 上显式声明参数"
        )
    positional_only = sorted(
        name
        for name, parameter in parameters.items()
        if parameter.kind is inspect.Parameter.POSITIONAL_ONLY
    )
    if positional_only:
        raise ValueError(
            f"工具 '{tool.name}' 的 executor 含位置-only 参数，无法用关键字调用：{positional_only}"
        )
    var_positional = sorted(
        name
        for name, parameter in parameters.items()
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL
    )
    if var_positional:
        raise ValueError(
            f"工具 '{tool.name}' 的 executor 含 *args，Schema 无法与之互相校验：{var_positional}"
        )
    undeclared = sorted(
        name
        for name, parameter in parameters.items()
        if parameter.kind in required_parameter_kinds and name not in schema_properties
    )
    if undeclared:
        raise ValueError(f"工具 '{tool.name}' 的 executor 参数未在 Schema 声明：{undeclared}")
