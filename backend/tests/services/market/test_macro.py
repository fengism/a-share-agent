"""单元测试：宏观数据服务测试。

注意：这些测试会调用外部 API，需要网络连接。
如果网络不可用或 API 超时，测试会跳过而非失败。
"""
import pytest

from app.utils.data_clean import safe_float, safe_int, safe_string


class TestDataClean:
    """data_clean 工具函数测试"""

    def test_safe_float_valid(self):
        assert safe_float("3.14") == 3.14
        assert safe_float(42) == 42.0
        assert safe_float("100", scale=100) == 1.0

    def test_safe_float_invalid(self):
        assert safe_float(None) is None
        assert safe_float("N/A") is None
        assert safe_float("-") is None
        assert safe_float("") is None

    def test_safe_int_valid(self):
        assert safe_int("42") == 42
        assert safe_int(3.14) == 3

    def test_safe_int_invalid(self):
        assert safe_int(None) is None
        assert safe_int("N/A") is None

    def test_safe_string_valid(self):
        assert safe_string(" hello ") == "hello"
        assert safe_string(123) == "123"

    def test_safe_string_invalid(self):
        assert safe_string(None) is None
        assert safe_string(float("nan")) is None


# ── data_clean 工具函数单元测试 ──

from app.utils.data_clean import safe_float, safe_int, safe_string


class TestDataClean:
    """data_clean 工具函数测试"""

    def test_safe_float_valid(self):
        assert safe_float("3.14") == 3.14
        assert safe_float(42) == 42.0
        assert safe_float("100", scale=100) == 1.0

    def test_safe_float_invalid(self):
        assert safe_float(None) is None
        assert safe_float("N/A") is None
        assert safe_float("-") is None
        assert safe_float("") is None

    def test_safe_int_valid(self):
        assert safe_int("42") == 42
        assert safe_int(3.14) == 3

    def test_safe_int_invalid(self):
        assert safe_int(None) is None
        assert safe_int("N/A") is None

    def test_safe_string_valid(self):
        assert safe_string(" hello ") == "hello"
        assert safe_string(123) == "123"

    def test_safe_string_invalid(self):
        assert safe_string(None) is None
        assert safe_string(float("nan")) is None
