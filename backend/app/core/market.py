import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

logger = logging.getLogger(__name__)

SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
"""A 股与港股业务日期基准时区。"""


def market_today() -> date:
    """返回市场时区（Asia/Shanghai）的当天日期。

    容器通常以 UTC 运行，而用户在浏览器里看到的是 Asia/Shanghai 日期。
    每天 00:00–08:00 CST 两者相差一天，若用 ``date.today()`` 校验「不能晚于今天」，
    用户提交的当日日期会被误判为未来日期而报错，因此业务日期一律走本函数。
    """
    return datetime.now(SHANGHAI_TIMEZONE).date()


@dataclass(frozen=True)
class SymbolFormats:
    """Stock code formats used by provider APIs."""

    raw: str
    prefixed_upper: str
    prefixed_lower: str
    exchange: str


def classify_exchange(code: str) -> str:
    """Classify the exchange of a six-digit mainland-listed security code."""
    code = code.strip()
    if not code.isdigit() or len(code) != 6:
        raise ValueError(f"无效股票代码: {code}，需要6位数字")
    if code.startswith(("5", "6", "900")):
        return "SH"
    if code.startswith(("0", "1", "2", "3")):
        return "SZ"
    if code.startswith(("4", "8", "920")):
        return "BJ"
    raise ValueError(f"无法识别交易所: {code}")


def normalize_code(raw: str) -> SymbolFormats:
    """Normalize a stock code into the formats used by provider APIs."""
    raw = raw.strip()
    for prefix in ("SH", "SZ", "BJ", "sh", "sz", "bj"):
        if raw.upper().startswith(prefix):
            raw = raw[len(prefix):]
            break

    if not raw.isdigit() or len(raw) != 6:
        raise ValueError(f"无效股票代码: {raw}，需要6位数字")

    exchange = classify_exchange(raw)
    result = SymbolFormats(
        raw=raw,
        prefixed_upper=f"{exchange}{raw}",
        prefixed_lower=f"{exchange.lower()}{raw}",
        exchange=exchange,
    )
    logger.debug(f"代码标准化: input→{result.raw}, exchange={result.exchange}")
    return result


def normalize_index_symbol(symbol: str) -> str:
    """Add a Sina-compatible prefix to an index symbol."""
    if symbol.startswith(("sh", "sz", "bj")):
        return symbol
    if symbol.startswith(("8", "4", "92")):
        return f"bj{symbol}"
    if symbol.startswith("0"):
        return f"sh{symbol}"
    return f"sz{symbol}"


def normalize_index_code(symbol: str) -> str:
    """Strip the market prefix from an index symbol."""
    if symbol.startswith(("sh", "sz", "bj")):
        return symbol[2:]
    return symbol


def normalize_stock_name(name: str) -> str:
    """Strip whitespace from a stock name."""
    return str(name or "").strip().replace(" ", "")


_A_SHARE_CODE_PREFIXES = frozenset({"00", "30", "60", "68", "43", "83", "87"})
A_SHARE_CODE_PATTERN_TEXT = r"(?:(?:00|30|60|68|43|83|87)\d{4})|(?:920\d{3})"


def is_a_share_code(code: str) -> bool:
    """校验 6 位 A 股代码（沪 60/68、深 00/30、北 43/83/87/920）。

    此前产业链等模块各自维护正则，92 前缀口径不一（920 才是北交所新段），
    统一到本函数。
    """
    text = str(code or "").strip()
    if len(text) != 6 or not text.isdigit():
        return False
    return text[:2] in _A_SHARE_CODE_PREFIXES or text[:3] == "920"


HK_STOCK_CODE_PATTERN_TEXT = r"(?:hk)?\d{1,5}"
"""港股代码正则文本（1-5 位数字，可带 ``hk`` 前缀）。

同时供运行时判定（``is_hk_code``）与 HTTP 路径约束使用，避免两处口径漂移：
路径只放行 6 位会让港股分析在提交阶段就被 422 挡掉。
"""

_HK_CODE_PATTERN = re.compile(rf"^({HK_STOCK_CODE_PATTERN_TEXT})$", re.IGNORECASE)

STOCK_CODE_PATH_PATTERN = rf"^(?:{A_SHARE_CODE_PATTERN_TEXT}|{HK_STOCK_CODE_PATTERN_TEXT})$"
"""A 股或港股代码的 HTTP 路径约束。"""


def is_hk_code(code: str) -> bool:
    """校验港股代码（1-5 位数字，可带 ``hk`` 前缀）。

    与 A 股 6 位口径天然互斥，因此调用方只凭代码即可判断市场归属，不必额外传参。
    与 ``financial_data.hk.service.normalize_hk_code`` 的正则保持一致。
    """
    return _HK_CODE_PATTERN.fullmatch(str(code or "").strip()) is not None


def contains_stock_reference(text: str, code: str, code_name: str) -> bool:
    """Check whether text references a stock by code or name alias."""
    code_base = normalize_stock_name(code_name)
    code_name_aliases = {code_base}
    for prefix in ("*ST", "ST", "N", "C", "XD", "DR", "XR"):
        if code_base.startswith(prefix) and len(code_base) > len(prefix):
            code_name_aliases.add(code_base[len(prefix):])
    code_name_aliases = sorted((alias for alias in code_name_aliases if alias), key=len, reverse=True)
    text = str(text or "")
    if not text:
        return False
    if code and code in text:
        return True
    return any(alias in text for alias in code_name_aliases)


def safe_float(value, scale: float = 1) -> float | None:
    """Convert a provider value to float, returning None for missing data."""
    if value is None or pd.isna(value) or value in ("N/A", "-", ""):
        return None
    try:
        return float(value) / scale
    except (ValueError, TypeError):
        return None


def safe_int(value) -> int | None:
    """Convert a provider value to int, returning None for missing data."""
    if value is None or pd.isna(value) or value in ("N/A", "-", ""):
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def safe_string(value) -> str | None:
    """Convert a provider value to a stripped string or None."""
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None
