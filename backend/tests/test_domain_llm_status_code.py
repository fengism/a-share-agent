"""``app.domain.llm.llm_error_status_code`` 的契约测试。

这个函数是「重试退避 / 降级判据 / 错误文案」三处的唯一状态码来源，
被抽出来之前 completion.py 里还有一份重复实现。行为必须唯一且明确。
"""

from __future__ import annotations

import pytest

from app.domain.llm import llm_error_status_code


class _StatusError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _ResponseError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.response = _Response(status_code)


def test_returns_none_without_status_code():
    assert llm_error_status_code(Exception("boom")) is None


def test_reads_status_code_attribute():
    assert llm_error_status_code(_StatusError("rate limited", status_code=429)) == 429


def test_reads_nested_response_status_code():
    """httpx/openai 的部分异常把状态码放在 response 上。"""
    assert llm_error_status_code(_ResponseError("nope", status_code=403)) == 403


def test_walks_cause_chain():
    inner = _StatusError("rate limited", status_code=429)
    outer = RuntimeError("wrapped")
    outer.__cause__ = inner
    assert llm_error_status_code(outer) == 429


def test_outermost_status_code_wins():
    """外层包装的那层才是真正的失败原因，不能被内层的状态码覆盖。"""
    inner = _StatusError("inner", status_code=429)
    outer = _StatusError("outer", status_code=400)
    outer.__cause__ = inner
    assert llm_error_status_code(outer) == 400


def test_ignores_non_integer_status_code():
    class Weird(Exception):
        status_code = "429"

    assert llm_error_status_code(Weird("string status")) is None


def test_does_not_substring_match_message():
    """14290 里的 "429" 绝不能被当成限流——这正是当初删掉裸子串匹配的原因。"""
    error = Exception("max_tokens 14290 exceeds the limit")
    assert llm_error_status_code(error) is None


def test_respects_max_depth():
    """链条超过深度上限时返回 None，不无限遍历。"""
    current: Exception = Exception("root")
    for index in range(12):
        wrapper = Exception(f"wrap-{index}")
        wrapper.__cause__ = current
        current = wrapper
    assert llm_error_status_code(current) is None


@pytest.mark.parametrize("status_code", [400, 401, 402, 403, 404, 422, 429, 500, 503])
def test_passes_through_common_codes(status_code: int):
    assert llm_error_status_code(_StatusError("x", status_code=status_code)) == status_code


def test_real_openai_api_status_error():
    """真实 SDK 异常能穿过包装层拿到状态码（不靠 mock 的假属性）。"""
    import httpx
    from openai import APIStatusError

    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    response = httpx.Response(429, request=request, json={"error": {"message": "rate limited"}})
    error = APIStatusError("rate limited", response=response, body=None)
    assert llm_error_status_code(error) == 429

    wrapper = RuntimeError("caller wrapped it")
    wrapper.__cause__ = error
    assert llm_error_status_code(wrapper) == 429

