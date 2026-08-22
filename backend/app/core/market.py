import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SymbolFormats:
    """Stock code formats used by provider APIs."""

    raw: str
    prefixed_upper: str
    prefixed_lower: str
    exchange: str


def classify_exchange(code: str) -> str:
    """Classify the exchange of a six-digit stock code."""
    code = code.strip()
    if not code.isdigit() or len(code) != 6:
        raise ValueError(f"无效股票代码: {code}，需要6位数字")
    if code.startswith("6") or code.startswith("900"):
        return "SH"
    if code.startswith(("0", "2", "3")):
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
    if symbol.startswith(("sh", "sz")):
        return symbol
    if symbol.startswith("0"):
        return f"sh{symbol}"
    return f"sz{symbol}"


def normalize_index_code(symbol: str) -> str:
    """Strip the market prefix from an index symbol."""
    if symbol.startswith(("sh", "sz")):
        return symbol[2:]
    return symbol


def normalize_stock_name(name: str) -> str:
    """Strip whitespace from a stock name."""
    return str(name or "").strip().replace(" ", "")


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
