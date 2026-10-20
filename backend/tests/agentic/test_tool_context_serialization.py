"""Tool-context serialization contract.

These functions decide what the model is allowed to see, and they run on every
tool result in every round, so both the shape guarantees and the exact-size
guarantees are pinned here:

- a truncated success stays ``ok: true`` and stays valid JSON;
- a truncated *failure* never flips to ``ok: true`` (a model that sees success
  stops retrying a dead call);
- the preview is maximal: adding one more character would exceed the budget.
"""

from __future__ import annotations

import json

from app.agentic.tools.document_output import bounded_document
from app.agentic.tools.serialization import (
    serialize_context_result,
    serialize_context_results,
    serialize_truncated_error,
    serialize_truncated_preview,
)

_NOTE = "Agent 工具上下文预算不足，结果已截断"


def _payload() -> str:
    return json.dumps(
        {
            "ok": True,
            "data": [
                {"code": f"{index:06d}", "name": "股票名称", "value": index * 1.5}
                for index in range(400)
            ],
        },
        ensure_ascii=False,
    )


def test_preview_is_valid_json_and_within_budget():
    content = _payload()

    for limit in (200, 1_000, 4_096, 12_000):
        preview = serialize_truncated_preview(content, _NOTE, limit)
        assert len(preview) <= limit
        parsed = json.loads(preview)
        assert parsed["ok"] is True
        assert parsed["meta"]["truncated"] is True
        assert parsed["data"]["preview"]


def test_preview_is_maximal():
    content = _payload()

    for limit in (1_000, 4_096):
        preview = serialize_truncated_preview(content, _NOTE, limit)
        parsed = json.loads(preview)
        take = len(parsed["data"]["preview"])
        # One more character would not fit any more.
        too_long = json.dumps(
            {"ok": True, "data": {"preview": content[: take + 1]},
             "meta": {"truncated": True, "reason": _NOTE}},
            ensure_ascii=False,
        )
        assert len(too_long) > limit


def test_preview_handles_escaping_heavy_content():
    content = 'he said "hi" \\ ok \n\r\t' * 2_000

    preview = serialize_truncated_preview(content, _NOTE, 2_000)

    assert len(preview) <= 2_000
    parsed = json.loads(preview)
    # Escapes survive the round trip instead of being mangled by byte counting.
    assert '"hi"' in parsed["data"]["preview"]
    assert "\n" in parsed["data"]["preview"]


def test_preview_returns_short_content_verbatim():
    preview = serialize_truncated_preview("短内容", _NOTE, 4_096)

    assert len(preview) <= 4_096
    assert json.loads(preview)["data"]["preview"] == "短内容"


def test_preview_degrades_safely_on_tiny_budgets():
    content = _payload()

    assert serialize_truncated_preview(content, _NOTE, 0) == ""
    for limit in (1, 2, 10, 40):
        assert len(serialize_truncated_preview(content, _NOTE, limit)) <= limit


def test_truncated_failure_never_flips_to_success():
    content = json.dumps({"ok": False, "error": {"code": "upstream_unavailable",
                                                 "message": "m" * 5_000, "retryable": True}})

    bounded = serialize_context_result(content, 300)

    assert len(bounded) <= 300
    parsed = json.loads(bounded)
    assert parsed["ok"] is False
    assert parsed["error"]["code"] == "upstream_unavailable"


def test_truncated_error_drops_detail_before_lying_about_the_code():
    bounded = serialize_truncated_error(
        {"code": "timeout", "message": "m" * 10_000, "retryable": True},
        "x" * 10_000,
        _NOTE,
        80,
    )

    assert len(bounded) <= 80
    parsed = json.loads(bounded)
    assert parsed["ok"] is False
    # The code survives even when the message and preview do not.
    assert parsed["error"]["code"] == "timeout"


def test_context_result_keeps_small_payloads_untouched():
    content = '{"ok":true,"data":{"v":1}}'

    assert serialize_context_result(content, 4_096) == content


def test_context_results_share_the_batch_budget_fairly():
    contents = [
        json.dumps({"ok": True, "data": [{"i": index}] * 200}, ensure_ascii=False)
        for index in range(4)
    ]

    bounded = serialize_context_results(contents, 2_000)

    assert sum(len(item) for item in bounded) <= 2_000
    # Every result keeps a usable share instead of the first one eating everything.
    assert all(len(item) > 100 for item in bounded)
    assert all(json.loads(item)["ok"] is True for item in bounded)


def test_context_results_prefer_small_results():
    small = '{"ok":true,"data":{"v":1}}'
    large = _payload()

    bounded = serialize_context_results([large, small], 4_000)

    assert bounded[1] == small  # small payload kept in full
    assert len(bounded[0]) <= 4_000 - len(small)


def test_bounded_document_keeps_continuation_metadata():
    text = "## 第 1 页\n" + "正文内容。" * 5_000
    document = {"title": "年报", "url": "https://example.com/a", "content": text, "content_type": "html"}

    bounded = bounded_document(document, 2_000)

    assert bounded is not None
    assert len(bounded) <= 2_000
    parsed = json.loads(bounded)
    assert parsed["data"]["truncated"] is True
    assert parsed["data"]["content_length"] == len(text)
    assert parsed["data"]["returned_characters"] < len(text)
    assert parsed["data"]["continuation_note"]


def test_preview_degrades_to_empty_json_object_when_the_envelope_cannot_fit():
    """信封本身就装不下时必须是 "{}"，不能是空串（role=tool 空内容有网关风险）。"""
    content = _payload()

    for limit in (2, 10, 40, 89):
        assert serialize_truncated_preview(content, _NOTE, limit) == "{}"
        assert serialize_context_result(content, limit) == "{}"


# --- 复用同一次 decode：截断时的证据判定不该再解析一遍整包 -------------------


def test_detailed_variant_flags_unknown_when_payload_fits():
    """未截断就没有解析，也就没有可复用的判定——必须返回 None 让调用方自己决定。"""
    from app.agentic.tools.serialization import serialize_context_results_detailed

    payload = '{"ok":true,"data":{"value":1}}'
    [(bounded, flag)] = serialize_context_results_detailed([payload], 10_000)
    assert bounded == payload
    assert flag is None


def test_detailed_variant_flag_matches_the_standalone_check():
    """复用 decode 的前提：结论必须与独立解析完全一致。"""
    from app.agentic.tools.serialization import (
        has_meaningful_tool_content,
        serialize_context_results_detailed,
    )

    payloads = [
        '{"ok":true,"data":[{"a":1},{"a":2}]}',
        '{"ok":true,"data":{}}',
        '{"ok":true,"data":[]}',
        '{"ok":true,"data":null}',
        '{"ok":true,"data":"   "}',
        '{"ok":false,"error":{"code":"upstream_unavailable","message":"boom"}}',
        '{"ok":false}',
        '{"value":0}',
        'not json at all',
        '{"truncated":',
        '{"ok":true,"data":{"items":[1,2,3]}}',
        "null",
    ]
    for payload in payloads:
        # 预算比载荷少一个字符：强制走截断分支（否则不会解析，也就没有可复用的判定）。
        limit = max(2, len(payload) - 1)
        (bounded, flag), = serialize_context_results_detailed([payload], limit)
        assert bounded  # 预算 8 也必须给出可用的替代内容
        assert flag == has_meaningful_tool_content(payload), payload


def test_detailed_variant_shares_the_batch_budget():
    from app.agentic.tools.serialization import (
        serialize_context_results,
        serialize_context_results_detailed,
    )

    contents = ['{"ok":true,"data":{"i":1}}' * 200, '{"ok":true,"data":{"i":2}}']
    plain = serialize_context_results(contents, 4_000)
    detailed = serialize_context_results_detailed(contents, 4_000)
    assert [bounded for bounded, _ in detailed] == plain
    assert detailed[1][1] is None  # 小结果未截断
    assert detailed[0][1] is True  # 大结果被截断，但数据本身有效


def test_precomputed_acquisition_flag_never_overrides_an_error():
    from app.agentic.semantics import EvidenceState

    assert EvidenceState.from_content("{}", is_error=True, acquired=True).acquired is False
    assert EvidenceState.from_content("{}", is_error=False, acquired=False).acquired is False
    # None 表示“没判定过”，仍走解析。
    assert EvidenceState.from_content('{"ok":true,"data":{"v":1}}').acquired is True
    assert EvidenceState.from_content("{}").acquired is False


# --- role=tool 的 content 任何预算下都必须是合法 JSON -------------------------


def test_no_budget_can_produce_an_empty_tool_message():
    """空串进 role=tool 的 content 会被部分网关判为 400；null 有时也放不下。"""
    content = _payload()

    for limit in range(0, 400):
        bounded = serialize_context_result(content, limit)
        assert bounded, f"limit={limit} 产出了空 content"
        json.loads(bounded)  # 必须是合法 JSON


def test_batch_budget_never_yields_empty_messages():
    contents = [_payload(), "{}", ""]

    for budget in range(0, 60):
        bounded = serialize_context_results(contents, budget)
        assert len(bounded) == len(contents)
        for item in bounded:
            assert item
            json.loads(item)


def test_empty_tool_output_is_normalized():
    assert serialize_context_result("", 1_000) == "{}"
    assert json.loads(serialize_context_result("", 0)) == {}


def test_dropped_result_placeholder_is_used_before_empty_string():
    from app.agentic.tools.serialization import EMPTY_TOOL_RESULT

    # 错误信封：预算够放 null 时用 null（明确「不是成功」），否则退回 {}。
    oversized = '{"ok":false,"error":{"code":"x","message":"%s"}}' % ("长" * 400)
    assert serialize_context_result(oversized, 4) == "null"
    assert serialize_context_result(oversized, 3) == EMPTY_TOOL_RESULT
