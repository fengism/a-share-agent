import json
from typing import Any

from app.agentic.protocol import ToolCallInfo

MAX_RESULT_LEN = 12000


def tool_call_cache_key(call: ToolCallInfo) -> str:
    """Create a stable cache key independent of JSON whitespace and key order."""
    arguments = call.function.arguments
    try:
        arguments = json.dumps(
            json.loads(arguments),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        arguments = arguments.strip()
    return f"{call.function.name}:{arguments}"


def serialize_truncated_preview(content: str, note: str) -> str:
    low = 0
    high = min(len(content), MAX_RESULT_LEN)
    best = json.dumps(
        {
            "ok": True,
            "data": {"preview": ""},
            "meta": {"truncated": True, "reason": note},
        },
        ensure_ascii=False,
    )
    while low <= high:
        middle = (low + high) // 2
        candidate = json.dumps(
            {
                "ok": True,
                "data": {"preview": content[:middle]},
                "meta": {"truncated": True, "reason": note},
            },
            ensure_ascii=False,
        )
        if len(candidate) <= MAX_RESULT_LEN:
            best = candidate
            low = middle + 1
        else:
            high = middle - 1
    return best


def _mapping_error_message(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    error = result.get("error")
    if not error:
        return None
    if isinstance(error, str):
        return error.strip() or None
    return json.dumps(error, ensure_ascii=False, default=str)


def result_error_message(result: Any) -> str | None:
    """Return fatal tool-reported errors while preserving partial batch results."""
    if isinstance(result, dict):
        return _mapping_error_message(result)
    if not isinstance(result, list) or not result:
        return None

    messages = [_mapping_error_message(item) for item in result]
    if any(message is None for message in messages):
        return None
    unique_messages = list(dict.fromkeys(message for message in messages if message))
    details = "；".join(unique_messages[:3])
    if len(unique_messages) > 3:
        details = f"{details}；另有 {len(unique_messages) - 3} 类错误"
    return f"全部 {len(result)} 项失败：{details}"


def serialize_result(result: Any) -> str:
    """Serialize a result using the stable JSON tool contract."""
    if error_message := result_error_message(result):
        context = (
            {key: value for key, value in result.items() if key != "error"}
            if isinstance(result, dict)
            else result
        )
        return serialize_error(
            "tool_reported_error",
            error_message,
            data=context or None,
        )

    payload = {"ok": True, "data": result}
    content = json.dumps(payload, ensure_ascii=False, default=str)
    if len(content) <= MAX_RESULT_LEN:
        return content

    if isinstance(result, list) and result:
        total = len(result)
        kept = total
        while kept > 1:
            kept //= 2
            payload = {
                "ok": True,
                "data": result[:kept],
                "meta": {
                    "truncated": True,
                    "reason": f"共 {total} 条，已保留前 {kept} 条",
                    "total_items": total,
                    "returned_items": kept,
                },
            }
            content = json.dumps(payload, ensure_ascii=False, default=str)
            if len(content) <= MAX_RESULT_LEN:
                return content
        single = json.dumps(result[0], ensure_ascii=False, default=str)
        return serialize_truncated_preview(single, "单条结果过长，已截断")

    raw_result = json.dumps(result, ensure_ascii=False, default=str)
    return serialize_truncated_preview(raw_result, "结果过长，已截断")


def serialize_error(
    code: str,
    message: str,
    *,
    retryable: bool = False,
    data: Any | None = None,
) -> str:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": code,
            "message": message[:2000],
            "retryable": retryable,
        },
    }
    if data is not None:
        payload["data"] = data
    content = json.dumps(payload, ensure_ascii=False, default=str)
    if len(content) <= MAX_RESULT_LEN:
        return content

    payload["data"] = {"omitted": True}
    payload["meta"] = {
        "truncated": True,
        "reason": "错误上下文过长，已省略",
    }
    return json.dumps(payload, ensure_ascii=False, default=str)
