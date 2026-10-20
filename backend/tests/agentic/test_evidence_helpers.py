"""Shared evidence payload helpers and user-safe failure labels."""

import json

from app.agentic.runtime.evidence import (
    decode_tool_payload,
    flatten_text,
    has_finite_number,
    tool_failure_label,
)


def test_decode_tool_payload_unwraps_ok_data_envelope():
    assert decode_tool_payload(json.dumps({"ok": True, "data": {"code": "600519"}})) == {
        "code": "600519"
    }


def test_decode_tool_payload_keeps_plain_text():
    assert decode_tool_payload("plain text body") == "plain text body"


def test_flatten_text_recurses_through_containers():
    assert flatten_text({"a": ["x", {"b": "y"}], "c": 1}) == "x\ny\n1"


def test_has_finite_number_rejects_bools_and_infinities():
    assert has_finite_number({"revenue": 1.5})
    assert not has_finite_number({"revenue": True})
    assert not has_finite_number({"revenue": float("inf")})
    assert not has_finite_number({"revenue": float("nan")})


def test_tool_failure_label_never_exposes_raw_provider_text():
    content = json.dumps({
        "ok": False,
        "error": {
            "code": "upstream_unavailable",
            "message": "provider secret: internal host unreachable",
        },
    })

    label = tool_failure_label(content)

    assert label == "数据源暂不可用"
    assert "secret" not in label
    assert "internal host" not in label


def test_tool_failure_label_falls_back_to_generic_text():
    assert tool_failure_label("not-json") == "工具调用失败"
    assert tool_failure_label(json.dumps({"ok": False, "error": {"code": "unknown_code"}})) == "工具调用失败"


def test_failure_code_fast_path_skips_decoding_success_payloads():
    from app.agentic.runtime.evidence import failure_label, safe_tool_failure_code

    # No "error" key -> no decode at all, and no false negative either.
    assert safe_tool_failure_code('{"ok":true,"data":{"items":[1,2,3]}}') == ""
    assert safe_tool_failure_code("plain text") == ""
    # The fast path must not miss envelopes whose data merely mentions the word.
    assert safe_tool_failure_code(
        '{"ok":false,"error":{"code":"timeout","message":"has \\"error\\" inside"}}'
    ) == "timeout"
    assert failure_label("timeout") == "数据获取超时"
    assert failure_label("") == "工具调用失败"


def test_evidence_state_reuses_the_acquisition_result_for_identical_context():
    from app.agentic.semantics import EvidenceState

    content = '{"ok":true,"data":{"code":"600519"}}'
    same = EvidenceState.from_content(content, context=content)
    truncated = EvidenceState.from_content(content, context='{"ok":true,"data":{}}')

    assert same.usable_acquisition is True
    assert same.usable_context is True
    # A truncated context that lost the payload is no longer evidence.
    assert truncated.usable_acquisition is True
    assert truncated.usable_context is False
