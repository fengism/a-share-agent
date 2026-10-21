import json
import re
from typing import Any

from app.agentic.protocol import ToolCallInfo
from app.agentic.tools.document_output import bounded_document

MAX_RESULT_LEN = 12000

# 工具自报的 error_code 只允许是本仓库自己的标识符形态，防止任意字符串成为
# 事件层的分支条件。
_REPORTED_ERROR_CODE = re.compile(r"[a-z][a-z0-9_]{0,63}")
# 框架自己发出的保留码：它们在事件层有专门语义（skipped / 会话预算耗尽）。
# 工具返回值里的 error_code 是数据，若透传保留码，一次真实执行过的调用会被
# 显示成「未实际执行」，模型据此认为「我没调过」而重调——正好放大成死循环。
_RESERVED_ERROR_CODES = frozenset(
    {
        "tool_budget_exceeded",
        "tool_context_budget_exhausted",
        "duplicate_tool_call",
        "deadline_exceeded",
    }
)
# 预算耗尽到连 {"ok": false}（12 字符）都放不下时的最小标记。
_DROPPED_RESULT = "null"
_MIN_DROPPED_RESULT_LEN = len(_DROPPED_RESULT)
# 工具消息的最小合法占位：role=tool 的 content 不能是空串（部分网关直接 400），
# 而 "{}" 只有 2 个字符、也不是有效证据（``_has_meaningful_value({})`` 为 False）。
EMPTY_TOOL_RESULT = "{}"


# Collection envelopes must be judged by their actual records, not request
# echoes, pagination counters or instructions describing how to use the tool.
_RESULT_COLLECTIONS = frozenset({"results", "items", "rows"})
_COLLECTION_METADATA = frozenset({
    "query", "engine", "count", "total", "total_count", "page", "page_size", "page_number",
    "offset", "limit", "has_more", "next_page", "next_cursor", "cursor", "columns",
    "detail_hint", "message", "status", "code", "url", "source_url", "link", "source",
    "time_range", "language", "fetched_at", "retrieved_at", "elapsed_ms", "meta", "metadata",
})


def _has_record_content(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("ok") is False or value.get("error"):
            return False
        if "data" in value:
            return _has_record_content(value["data"])
        return any(_has_record_content(item) for key, item in value.items()
                   if key not in _COLLECTION_METADATA and key not in {"ok", "error"})
    if isinstance(value, list):
        return any(_has_record_content(item) for item in value)
    return _has_meaningful_value(value)


def _has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (bool, int, float)):
        return True
    if isinstance(value, list):
        return any(_has_meaningful_value(item) for item in value)
    if isinstance(value, dict):
        envelope_ok = value.get("ok")
        if envelope_ok is False:
            return False
        if isinstance(envelope_ok, bool):
            if "data" in value:
                return _has_meaningful_value(value["data"])
            return any(
                _has_meaningful_value(item)
                for key, item in value.items()
                if key not in {"ok", "error", "meta"}
            )
        if _RESULT_COLLECTIONS.intersection(value):
            return _has_record_content(value)
        return any(_has_meaningful_value(item) for item in value.values())
    return bool(str(value).strip())


def has_meaningful_tool_content(content: str) -> bool:
    """Return whether serialized Tool content contains usable evidence."""
    stripped = content.strip()
    if not stripped:
        return False
    try:
        payload = json.loads(stripped)
    except (TypeError, ValueError, json.JSONDecodeError):
        return True
    return _has_meaningful_value(payload)


def _cache_key(name: str, arguments: str, user_id: int | str | None) -> str:
    if user_id is None:
        return f"{name}:{arguments}"
    return f"{name}:user:{user_id}:{arguments}"


def tool_call_cache_key_from_arguments(
    name: str,
    arguments: Any,
    *,
    user_id: int | str | None = None,
) -> str:
    """Create a cache key from already-parsed arguments (avoids a second decode)."""
    try:
        canonical = json.dumps(
            arguments,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError):
        canonical = str(arguments).strip()
    return _cache_key(name, canonical, user_id)


def tool_call_cache_key(call: ToolCallInfo, *, user_id: int | str | None = None) -> str:
    """Create a stable cache key independent of JSON whitespace and key order.

    ``user_id`` 用于 scope="user" 的工具：这类工具的结果依赖当前用户的私有配置
    （LLM api_key / model 等），不按用户分区就可能把一个用户的结果复用给另一个用户。
    """
    raw = call.function.arguments
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return _cache_key(call.function.name, raw.strip(), user_id)
    return tool_call_cache_key_from_arguments(call.function.name, parsed, user_id=user_id)


# ensure_ascii=False 下 JSON 只需要转义这三类字符；不含它们时序列化长度可以精确预算，
# 不用为了量长度把整包重新 encode 十几遍。
_JSON_ESCAPE_NEEDED = re.compile(r'["\\\x00-\x1f]')


def serialize_truncated_preview(
    content: str,
    note: str,
    max_result_len: int = MAX_RESULT_LEN,
) -> str:
    """Fit a prefix of ``content`` into a ``{ok, data.preview, meta}`` envelope.

    旧实现用二分查找并每步 ``json.dumps`` 整包：一次 15k 字符的结果要 encode
    ~19 次，在真实请求里占到 agent 侧 CPU 的 65%。现在先按「不转义时长 1:1」
    精确算出可放长度，命中就只序列化一次；只有真的含引号/反斜杠/控制字符时才
    用溢出回退收缩（至少 1:1 增长，1~2 次收敛）。
    """
    limit = max(0, int(max_result_len))
    envelope: dict[str, Any] = {
        "ok": True,
        "data": {"preview": ""},
        "meta": {"truncated": True, "reason": note},
    }
    base = json.dumps(envelope, ensure_ascii=False)
    # 空 preview 的 JSON 字面量 "" 占 2 个字符；剩余额度就是转义后 preview 的预算。
    budget = limit - (len(base) - 2)
    if budget < 2:
        # 信封本身都装不下。调用方会把超预算的返回值换成 "{}"，但这里直接给出
        # 合法的 "{}"：旧实现经调用方后也是 "{}“，改写成空串会变成
        # role=tool 的 content 为空（部分网关 400），是一个真实的协议回归。
        if len(base) <= limit:
            return base
        return "{}" if limit >= 2 else ""
    take = min(len(content), budget - 2)
    if not _JSON_ESCAPE_NEEDED.search(content, 0, take):
        envelope["data"]["preview"] = content[:take]
        return json.dumps(envelope, ensure_ascii=False)
    while take > 0:
        envelope["data"]["preview"] = content[:take]
        candidate = json.dumps(envelope, ensure_ascii=False)
        overflow = len(candidate) - limit
        if overflow <= 0:
            return candidate
        # 尾部被删掉的那段自己也可能含转义字符（JSON 载荷到处是引号）。
        # 按「字符 + 转义增量」估算要删多少，避免抽多后只剩一个小预览。
        tail_start = max(0, take - overflow)
        escaped = len(_JSON_ESCAPE_NEEDED.findall(content, tail_start, take))
        take -= max(1, overflow - escaped)
    envelope["data"]["preview"] = ""
    candidate = json.dumps(envelope, ensure_ascii=False)
    return candidate if len(candidate) <= limit else ""


def _truncated_error_envelope(
    code: str,
    message: str,
    retryable: bool,
    note: str,
    preview: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": {"code": code, "message": message, "retryable": retryable},
    }
    if preview is not None:
        payload["data"] = {"preview": preview}
    payload["meta"] = {"truncated": True, "reason": note}
    return payload


def serialize_truncated_error(
    error: Any,
    content: str,
    note: str,
    max_result_len: int,
) -> str:
    """Shrink an error envelope from the payload outward so ``ok`` never flips to true.

    ``serialize_truncated_preview`` hardcodes ``ok: true`` because truncating a
    successful payload cannot change the outcome. Applying it to ``ok: false``
    would rewrite a failure into a success (or into ``{}`` once nothing fit), and
    downstream readers such as ``result_error_message``/``_error_message`` only
    look at the outer envelope — so the model would stop retrying a dead call.

    Every candidate is measured against the budget: overshooting it would push
    the run past its protocol character limit.
    """
    limit = max(0, int(max_result_len))
    if not isinstance(error, dict):
        error = {"code": "tool_reported_error", "message": str(error or "")}
    code = str(error.get("code") or "tool_reported_error")[:80]
    retryable = bool(error.get("retryable"))
    message = str(error.get("message") or "")

    # 1) 保留完整错误信息，先牺牲载荷预览。
    if len(json.dumps(_truncated_error_envelope(code, message, retryable, note, ""), ensure_ascii=False)) <= limit:
        best = _truncated_error_envelope(code, message, retryable, note, "")
        low, high = 0, min(len(content), limit)
        while low <= high:
            middle = (low + high) // 2
            candidate = _truncated_error_envelope(code, message, retryable, note, content[:middle])
            if len(json.dumps(candidate, ensure_ascii=False)) <= limit:
                best = candidate
                low = middle + 1
            else:
                high = middle - 1
        return json.dumps(best, ensure_ascii=False)

    # 2) 光是错误信息就装不下：削 message，丢掉预览。
    low, high = 0, len(message)
    fitted: dict[str, Any] | None = None
    while low <= high:
        middle = (low + high) // 2
        candidate = _truncated_error_envelope(code, message[:middle], retryable, note, None)
        if len(json.dumps(candidate, ensure_ascii=False)) <= limit:
            fitted = candidate
            low = middle + 1
        else:
            high = middle - 1
    if fitted is not None:
        return json.dumps(fitted, ensure_ascii=False)

    # 3) 只剩错误码可放：报失败但仍不给细节，比谎报成功好。
    minimal = {"ok": False, "error": {"code": code, "message": "", "retryable": retryable}}
    if len(json.dumps(minimal, ensure_ascii=False)) <= limit:
        return json.dumps(minimal, ensure_ascii=False)
    bare = {"ok": False, "error": {"code": code}}
    if len(json.dumps(bare, ensure_ascii=False)) <= limit:
        return json.dumps(bare, ensure_ascii=False)
    if len(json.dumps({"ok": False})) <= limit:
        return json.dumps({"ok": False})
    # 预算只剩几个字符时用 null 而不是空串：空串进 role=tool 的 content 有协议风险
    # （部分网关 400），而 null 是合法 JSON、不会谎报成功、也不会被当成有效证据
    # （_has_meaningful_value(None) 为 False）。
    if limit >= _MIN_DROPPED_RESULT_LEN:
        return _DROPPED_RESULT
    # 放不下 null 时也不能给空串：{} 同样是「没有可用内容」，但不是非法协议载荷。
    return EMPTY_TOOL_RESULT


def serialize_context_result(content: str, max_result_len: int) -> str:
    bounded, _ = _serialize_context_result_detailed(content, max_result_len)
    return bounded


def _serialize_context_result_detailed(
    content: str,
    max_result_len: int,
) -> tuple[str, bool | None]:
    """Bound one payload, reusing the decode needed for truncation.

    Returns ``(bounded, source_has_evidence)``. ``source_has_evidence`` is ``None``
    when this path never decoded the payload (it fit the budget), so the caller must
    decide itself.

    上下文截断必然要 ``json.loads`` 整包，而调用方紧接着还要再解析一次同一份内容来
    判定「是否拿到有效证据」。一个 46k 的结果约 1.3ms，一次请求里每条结果就是 2.6ms
    的重复解码；这里把同一次 decode 的结果复用出去。
    """
    limit = max(0, int(max_result_len))
    if len(content) <= limit:
        # 工具自己返回空内容时同样补一个合法占位。
        return content or EMPTY_TOOL_RESULT, None
    if limit < len(EMPTY_TOOL_RESULT):
        # 预算连 {} 都放不下：仍然给出合法 JSON。最多超出 2 个字符，比一次
        # 因 role=tool 空内容而失败的请求便宜得多。
        return EMPTY_TOOL_RESULT, None
    try:
        envelope = json.loads(content)
    except (ValueError, TypeError):
        # 非 JSON 文本：与原 ``has_meaningful_tool_content`` 一致，按「有内容」处理。
        source_has_evidence: bool | None = True
        envelope = None
    else:
        source_has_evidence = _has_meaningful_value(envelope)
    if isinstance(envelope, dict) and envelope.get("ok") is False:
        note = "Agent 工具上下文预算不足，结果已截断"
        return serialize_truncated_error(envelope.get("error"), content, note, limit), source_has_evidence
    if isinstance(envelope, dict) and envelope.get("ok") is True:
        document = bounded_document(envelope.get("data"), limit, envelope.get("meta") or {})
        if document is not None:
            return document, source_has_evidence
    preview = serialize_truncated_preview(
        content,
        "Agent 工具上下文预算不足，结果已截断",
        limit,
    )
    return (preview if len(preview) <= limit else "{}"), source_has_evidence


def serialize_context_results(contents: list[str], max_result_len: int) -> list[str]:
    """Share a batch budget fairly; small results retain their full payload first."""
    return [bounded for bounded, _ in serialize_context_results_detailed(contents, max_result_len)]


def serialize_context_results_detailed(
    contents: list[str],
    max_result_len: int,
) -> list[tuple[str, bool | None]]:
    """``serialize_context_results`` plus each source payload's evidence flag.

    See ``_serialize_context_result_detailed`` for why the flag is free here.
    """
    remaining = max(0, int(max_result_len))
    bounded: list[tuple[str, bool | None]] = [("", None)] * len(contents)
    ordered = sorted(range(len(contents)), key=lambda index: len(contents[index]))
    for offset, index in enumerate(ordered):
        allowance = remaining // (len(ordered) - offset)
        bounded[index] = _serialize_context_result_detailed(contents[index], allowance)
        remaining -= len(bounded[index][0])
    return bounded


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


def reported_error_code(result: Any) -> str:
    """Use the tool's own ``error_code`` when it is one of our identifier-shaped codes.

    Without this every tool-reported failure collapsed into ``tool_reported_error``,
    so ``invalid_arguments`` from ``financial_calculator``/``python_interpreter``
    and ``upstream_unavailable`` from ``analyze_financials`` never reached the
    code-keyed diagnostics in ``events._tool_result_summary``.

    Reserved framework codes are rejected on the way through: ``error_code`` comes
    from a tool's return value, so letting it impersonate ``tool_budget_exceeded``
    would render a call that really ran as "未实际执行".
    """
    if isinstance(result, dict):
        code = result.get("error_code")
        if (
            isinstance(code, str)
            and _REPORTED_ERROR_CODE.fullmatch(code)
            and code not in _RESERVED_ERROR_CODES
        ):
            return code
    return "tool_reported_error"


_SEMANTIC_NULL_KEYS = frozenset(
    {
        # 核心估值指标（如亏损公司市盈率为 null，明确表明无有效估值倍数而非“未曾查询”）
        "pe", "pe_ttm", "pe_static", "pe_forward", "pb", "pb_mrq", "pb_3y", "ps", "ps_ttm", "ps_3y", "peg", "pcf", "pcf_ttm",
        # 核心盈利与回报率（如未分红公司股息率为 null）
        "eps", "basic_eps", "diluted_eps", "roe", "roa", "roic", "gross_margin", "net_margin", "dividend_yield", "dv_ratio", "dv_ttm",
        # 核心成长与财务杠杆
        "revenue_yoy", "net_profit_yoy", "operate_income_yoy", "parent_netprofit_yoy", "debt_asset_ratio", "asset_liability_ratio",
        "non_net_profit", "non_net_profit_yoy", "deduct_parent_netprofit", "deduct_parent_netprofit_yoy", "current_ratio", "quick_ratio",
        # 评级、目标价与市场概览
        "rating", "target_price", "upside_pct", "turnover_pct", "current_price", "market_cap", "float_market_cap",
        # 估值模型置信度与结果
        "confidence", "confidence_score", "target_multiple", "equity_value", "per_share_value",
    }
)


def _is_semantic_null_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in _SEMANTIC_NULL_KEYS or lowered.startswith("is_")


def compact_tool_payload(value: Any) -> Any:
    """Recursively strip None values from dicts, preserving distinct domain nulls."""
    if isinstance(value, dict):
        return {
            k: compact_tool_payload(v)
            for k, v in value.items()
            if v is not None or _is_semantic_null_key(str(k))
        }
    if isinstance(value, (list, tuple)):
        return [compact_tool_payload(item) for item in value]
    return value


def _find_item_timestamp(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    for key in ("date", "time", "datetime", "trade_date", "report_date", "日期", "交易日期", "报告期"):
        val = item.get(key) or item.get(key.upper())
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _slice_collection_items(items: list[Any], kept: int) -> tuple[list[Any], str]:
    """Slice collection to fit budget, preserving latest records if ordered chronologically."""
    if not items or kept >= len(items):
        return items, ""
    total = len(items)
    first_date = _find_item_timestamp(items[0])
    last_date = _find_item_timestamp(items[-1])
    if first_date and last_date:
        if first_date < last_date:
            # 升序时序数据（如 K 线）：保留最新（尾部）数据
            return items[-kept:], f"共 {total} 条，已保留最新 {kept} 条"
        else:
            # 降序时序数据（如新闻列表）：保留最新（头部）数据
            return items[:kept], f"共 {total} 条，已保留最新 {kept} 条"
    return items[:kept], f"共 {total} 条，已保留前 {kept} 条"


def serialize_result(result: Any, max_result_len: int = MAX_RESULT_LEN) -> str:
    """Serialize a result using the stable JSON tool contract."""
    if error_message := result_error_message(result):
        context = (
            {key: value for key, value in result.items() if key != "error"}
            if isinstance(result, dict)
            else result
        )
        return serialize_error(
            reported_error_code(result),
            error_message,
            data=context or None,
        )

    if isinstance(result, dict) and result.get("ok") is False:
        # 工具自报失败却没有可读原因（沙箱就允许 error 为空串）。不能因为
        # result_error_message 判空就把它包成 ok:true —— 那会让「失败」在模型眼里
        # 变成「成功但没有数据」。
        return serialize_error(
            reported_error_code(result),
            "工具返回了失败状态但未提供原因；请改用其他工具或来源，不要基于空结果下结论",
            data={key: value for key, value in result.items() if key != "ok"} or None,
        )

    compacted = compact_tool_payload(result)
    payload = {"ok": True, "data": compacted}
    content = json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
    if len(content) <= max_result_len:
        return content

    document = bounded_document(compacted, max_result_len)
    if document is not None:
        return document

    if isinstance(compacted, list) and compacted:
        total = len(compacted)
        kept = total
        while kept > 1:
            kept //= 2
            sliced, reason = _slice_collection_items(compacted, kept)
            payload = {
                "ok": True,
                "data": sliced,
                "meta": {
                    "truncated": True,
                    "reason": reason,
                    "total_items": total,
                    "returned_items": kept,
                },
            }
            content = json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
            if len(content) <= max_result_len:
                return content
        first_or_last = (
            compacted[-1]
            if (isinstance(compacted[0], dict) and _find_item_timestamp(compacted[0]))
            else compacted[0]
        )
        single = json.dumps(first_or_last, ensure_ascii=False, default=str, separators=(",", ":"))
        return serialize_truncated_preview(single, "单条结果过长，已截断", max_result_len)

    if isinstance(compacted, dict):
        for coll_key in ("items", "results", "rows", "records", "data", "list", "news"):
            coll = compacted.get(coll_key)
            if isinstance(coll, list) and len(coll) > 1:
                total = len(coll)
                kept = total
                while kept > 1:
                    kept //= 2
                    sliced, reason = _slice_collection_items(coll, kept)
                    truncated_dict = {**compacted, coll_key: sliced}
                    payload = {
                        "ok": True,
                        "data": truncated_dict,
                        "meta": {
                            "truncated": True,
                            "reason": reason,
                            "total_items": total,
                            "returned_items": kept,
                        },
                    }
                    content = json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
                    if len(content) <= max_result_len:
                        return content
                break

    raw_result = json.dumps(compacted, ensure_ascii=False, default=str, separators=(",", ":"))
    return serialize_truncated_preview(raw_result, "结果过长，已截断", max_result_len)


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
        payload["data"] = compact_tool_payload(data)
    content = json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
    if len(content) <= MAX_RESULT_LEN:
        return content

    payload["data"] = {"omitted": True}
    payload["meta"] = {
        "truncated": True,
        "reason": "错误上下文过长，已省略",
    }
    return json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
