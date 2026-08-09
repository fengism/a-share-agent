"""Agentic Tool 参数 Schema 与执行器契约校验。"""

import inspect
import json
import math
import re
from datetime import date
from typing import Any
from urllib.parse import urlsplit

SUPPORTED_SCHEMA_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}


class ToolArgumentsError(ValueError):
    """Tool arguments do not satisfy the declared JSON Schema."""


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
        raise ToolArgumentsError(f"{path} 类型错误，应为 {'/'.join(expected_types)}")

    if "enum" in schema and value not in schema["enum"]:
        raise ToolArgumentsError(f"{path} 必须是 {schema['enum']} 之一")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        missing = [name for name in schema.get("required", []) if name not in value]
        if missing:
            raise ToolArgumentsError(f"缺少必填参数：{', '.join(missing)}")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise ToolArgumentsError(f"包含未声明参数：{', '.join(extra)}")
        for name, item in value.items():
            if property_schema := properties.get(name):
                validate_value(item, property_schema, f"{path}.{name}")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ToolArgumentsError(f"{path} 至少需要 {schema['minItems']} 项")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ToolArgumentsError(f"{path} 最多允许 {schema['maxItems']} 项")
        if schema.get("uniqueItems"):
            normalized = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(normalized) != len(set(normalized)):
                raise ToolArgumentsError(f"{path} 不允许重复项")
        if item_schema := schema.get("items"):
            for index, item in enumerate(value):
                validate_value(item, item_schema, f"{path}[{index}]")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ToolArgumentsError(f"{path} 长度不能小于 {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ToolArgumentsError(f"{path} 长度不能超过 {schema['maxLength']}")
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, value) is None:
            raise ToolArgumentsError(f"{path} 格式不正确")
        if schema.get("format") == "date":
            try:
                date.fromisoformat(value)
            except ValueError as error:
                raise ToolArgumentsError(f"{path} 必须是有效的 YYYY-MM-DD 日期") from error
        if schema.get("format") == "uri":
            try:
                parsed = urlsplit(value)
                hostname = parsed.hostname
            except ValueError as error:
                raise ToolArgumentsError(f"{path} 必须是有效的 HTTP(S) URL") from error
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or not hostname:
                raise ToolArgumentsError(f"{path} 必须是有效的 HTTP(S) URL")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            raise ToolArgumentsError(f"{path} 必须是有限数值")
        if "minimum" in schema and value < schema["minimum"]:
            raise ToolArgumentsError(f"{path} 不能小于 {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ToolArgumentsError(f"{path} 不能大于 {schema['maximum']}")


def validate_schema(schema: dict[str, Any], path: str = "parameters") -> None:
    if not isinstance(schema, dict):
        raise ValueError(f"{path} 必须是对象")
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
