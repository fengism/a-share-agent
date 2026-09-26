"""工具执行失败的 retryable 判定策略。

修复前 ``Tool.execute`` 的兜底分支无条件 ``retryable=True``：``PermissionError("仅管理员
可以管理在线量化策略")``、``TypeError``、配置错误全都被标成「可重试」，模型看到就拿着
同样的参数原地重试，把工具配额和 LLM 往返浪费在同一个不会消失的错误上。

策略是白名单：只有明确的瞬时性异常（超时/连接类）才允许重试，其余默认不可重试，
并且在文案里直接告诉模型「原样重试无效」。
"""
import asyncio
import json

import httpx
import pytest
import requests

from app.agentic.protocol import ToolCallInfo
from app.agentic.tools.contracts import Tool, ToolPolicy
from app.core.errors import is_transient_error
from app.core.exceptions import (
    ApplicationError,
    InvalidRequestError,
    UpstreamUnavailableError,
)


class TestTransientPolicy:
    @pytest.mark.parametrize(
        "error",
        [
            TimeoutError(),
            asyncio.TimeoutError(),
            ConnectionResetError(),
            ConnectionRefusedError(),
            BrokenPipeError(),
            InterruptedError(),
        ],
    )
    def test_transient_errors_are_retryable(self, error):
        assert is_transient_error(error) is True

    @pytest.mark.parametrize(
        "error",
        [
            TypeError(),
            ValueError(),
            AttributeError(),
            KeyError(),
            PermissionError("仅管理员可以管理在线量化策略"),
            FileNotFoundError(),
            IsADirectoryError(),
            RuntimeError("当前请求缺少登录用户"),
            AssertionError(),
            ZeroDivisionError(),
            json.JSONDecodeError("Expecting value", "doc", 0),
        ],
    )
    def test_permanent_errors_are_not_retryable(self, error):
        assert is_transient_error(error) is False

    def test_osaerror_subclass_that_is_not_connection_stays_permanent(self):
        # OSError 家族里只有连接类是瞬时的：文件缺失不会因为重试出现。
        assert is_transient_error(OSError()) is False
        assert is_transient_error(ConnectionError()) is True


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class TestRealHttpClientExceptions:
    """实际 HTTP 栈用 requests；其异常与内置异常是兄弟类，必须显式登记。

    漏掉这一组的后果特别隐蔽：真实网络故障会被判成「不可重试」，而且工具层还会
    明确告诉模型「原样重试无效」——把可恢复的上游抖动变成硬失败。
    """

    @pytest.mark.parametrize(
        "error",
        [
            requests.exceptions.ConnectionError("connection reset by peer"),
            requests.exceptions.ConnectTimeout("connect timeout"),
            requests.exceptions.ReadTimeout("read timeout"),
            requests.exceptions.Timeout("timeout"),
            requests.exceptions.ChunkedEncodingError("truncated response"),
        ],
    )
    def test_requests_transport_errors_are_retryable(self, error):
        assert is_transient_error(error) is True

    @pytest.mark.parametrize("status", [408, 425, 429, 500, 502, 503, 504])
    def test_retryable_http_status(self, status: int):
        error = requests.exceptions.HTTPError(response=_FakeResponse(status))
        assert is_transient_error(error) is True

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
    def test_client_error_status_is_permanent(self, status: int):
        error = requests.exceptions.HTTPError(response=_FakeResponse(status))
        assert is_transient_error(error) is False

    def test_httpx_transport_error_is_retryable(self):
        assert is_transient_error(httpx.ConnectError("boom")) is True
        assert is_transient_error(httpx.ReadTimeout("boom")) is True

    async def test_tool_layer_treats_a_real_network_failure_as_retryable(self):
        async def boom():
            raise requests.exceptions.ConnectionError("connection reset by peer")

        payload = _payload(await _execute(boom))
        assert payload["error"]["retryable"] is True
        # 关键：不能再对模型说「原样重试无效」。
        assert "该错误不会因原样重试而消失" not in payload["error"]["message"]


async def _execute(executor, *, timeout_seconds: float | None = None):
    tool = Tool(
        name="stub_retryable",
        description="测试用",
        parameters={"type": "object", "properties": {}},
        executor=executor,
        policy=ToolPolicy(timeout_seconds=timeout_seconds),
    )
    return await tool.execute(
        ToolCallInfo(id="c1", function={"name": "stub_retryable", "arguments": "{}"})
    )


def _payload(result):
    return json.loads(result.content)


class TestToolLevelRetryable:
    @pytest.mark.parametrize(
        "error",
        [
            TypeError("'NoneType' object is not subscriptable"),
            PermissionError("仅管理员可以管理在线量化策略"),
            RuntimeError("当前请求缺少登录用户"),
            FileNotFoundError("数据库文件不存在"),
        ],
    )
    async def test_permanent_failures_are_marked_not_retryable(self, error):
        async def boom():
            raise error

        payload = _payload(await _execute(boom))
        assert payload["error"]["code"] == "execution_failed"
        assert payload["error"]["retryable"] is False
        assert "该错误不会因原样重试而消失" in payload["error"]["message"]

    async def test_connection_errors_stay_retryable(self):
        async def boom():
            raise ConnectionResetError("connection reset by peer")

        payload = _payload(await _execute(boom))
        assert payload["error"]["retryable"] is True
        assert "该错误不会因原样重试而消失" not in payload["error"]["message"]

    async def test_deadline_stays_retryable(self):
        async def slow():
            await asyncio.sleep(5)

        payload = _payload(await _execute(slow, timeout_seconds=1.0))
        assert payload["error"]["code"] == "timeout"
        assert payload["error"]["retryable"] is True

    async def test_upstream_unavailable_stays_retryable(self):
        async def boom():
            raise UpstreamUnavailableError("行情源 503")

        payload = _payload(await _execute(boom))
        assert payload["error"]["code"] == "upstream_unavailable"
        assert payload["error"]["retryable"] is True

    async def test_other_application_errors_are_not_retryable(self):
        async def boom():
            raise InvalidRequestError("参数不合法")

        payload = _payload(await _execute(boom))
        assert payload["error"]["code"] == "bad_request"
        assert payload["error"]["retryable"] is False

    async def test_generic_application_error_is_not_retryable(self):
        async def boom():
            raise ApplicationError("业务规则拒绝")

        payload = _payload(await _execute(boom))
        assert payload["error"]["code"] == "application_error"
        assert payload["error"]["retryable"] is False
