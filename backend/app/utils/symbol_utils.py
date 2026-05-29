import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SymbolFormats:
    raw: str  # "000001"
    prefixed_upper: str  # "SZ000001"
    prefixed_lower: str  # "sz000001"
    exchange: str  # "SZ"


def classify_exchange(code: str) -> str:
    code = code.strip()
    if not code:
        raise ValueError("股票代码为空")
    first = code[0]
    if first in ("6", "9"):
        return "SH"
    if first in ("0", "3"):
        return "SZ"
    if first == "8":
        return "BJ"
    raise ValueError(f"无法识别交易所: {code}")


def normalize_code(raw: str) -> SymbolFormats:
    raw = raw.strip()
    # 去掉可能的前缀
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
    if symbol.startswith(("sh", "sz")):
        return symbol
    if symbol.startswith("0"):
        return f"sh{symbol}"
    return f"sz{symbol}"


def normalize_index_symbol_v2(symbol: str) -> str:
    if symbol.startswith(("sh", "sz")):
        return symbol
    if symbol.startswith("6"):
        return f"sh{symbol}"
    return f"sz{symbol}"


def normalize_index_code(symbol: str) -> str:
    if symbol.startswith(("sh", "sz")):
        return symbol[2:]
    return symbol


def normalize_stock_name(name: str) -> str:
    return str(name or "").strip().replace(" ", "")


def contains_stock_reference(text: str, code: str, code_name: str) -> bool:
    code_base = normalize_stock_name(code)
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
