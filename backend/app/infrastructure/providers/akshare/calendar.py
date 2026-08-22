"""新浪 A 股交易日历的纯 Python 适配。"""

from datetime import date, timedelta

from app.constants.http import SINA_FINANCE_HEADERS
from app.infrastructure.http.client import provider_get

_TRADE_CALENDAR_URL = "https://finance.sina.com.cn/realstock/company/klc_td_sh.txt"
_BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_EPOCH = date(1970, 1, 1)
_SINA_EPOCH_OFFSET_DAYS = 7657
_SINA_TRADE_DATE_DECODER = 139


class _BitReader:
    def __init__(self, payload: str) -> None:
        try:
            self._values = [_BASE64_ALPHABET.index(character) for character in payload]
        except ValueError as exc:
            raise ValueError("新浪交易日历包含无效编码字符") from exc
        self._index = 0
        self._offset = 0

    def read_bool(self) -> bool:
        return bool(self.read_bits(1))

    def read_bits(self, width: int) -> int:
        value = 0
        shift = 0
        remaining = width
        while remaining > 0:
            if self._index >= len(self._values):
                raise ValueError("新浪交易日历编码不完整")
            bit_count = min(remaining, 6 - self._offset)
            mask = (1 << bit_count) - 1
            value |= ((self._values[self._index] >> self._offset) & mask) << shift
            self._offset += bit_count
            remaining -= bit_count
            shift += bit_count
            if self._offset >= 6:
                self._index += 1
                self._offset = 0
        return value

    def read_signed_run_length(self) -> int:
        positive = self.read_bool()
        magnitude = 1
        while self.read_bool():
            magnitude += 1
        return magnitude if positive else -magnitude


def _decode_sina_trade_dates(payload: str) -> list[date]:
    reader = _BitReader(payload)
    decoder = reader.read_bits(12)
    marker = reader.read_bits(6)
    if decoder != _SINA_TRADE_DATE_DECODER or (63 ^ marker) > 1:
        raise ValueError("新浪交易日历编码格式不受支持")

    bit_width_level = 0
    remaining_open_days = -1
    current_day = reader.read_bits(18) - 1
    last_day = reader.read_bits(18)
    trade_dates: list[date] = []

    while current_day < last_day:
        current_day += 1
        weekday = current_day % 7
        if weekday in (3, 4):
            current_day += 5 - weekday
        current_date = _EPOCH + timedelta(days=_SINA_EPOCH_OFFSET_DAYS + current_day)

        if remaining_open_days <= 0:
            if reader.read_bool():
                bit_width_level += reader.read_signed_run_length()
            if bit_width_level < 0:
                raise ValueError("新浪交易日历位宽无效")
            width = 3 * bit_width_level
            remaining_open_days = (reader.read_bits(width) if width else 0) + 1
            if not trade_dates:
                trade_dates.append(current_date)
                remaining_open_days -= 1
        else:
            trade_dates.append(current_date)
        remaining_open_days -= 1

    missing_trade_date = date(1992, 5, 4)
    if missing_trade_date not in trade_dates:
        trade_dates.append(missing_trade_date)
        trade_dates.sort()
    return trade_dates


def fetch_trade_dates() -> list[date]:
    """获取 A 股交易日期，不依赖 py_mini_racer。"""
    response = provider_get(
        _TRADE_CALENDAR_URL,
        headers=SINA_FINANCE_HEADERS,
        timeout=10,
    )
    _, separator, encoded_text = response.text.partition("=")
    if not separator:
        raise ValueError("新浪交易日历响应格式无效")
    payload = encoded_text.split(";", 1)[0].strip().strip('"')
    if not payload:
        raise ValueError("新浪交易日历响应为空")
    return _decode_sina_trade_dates(payload)
