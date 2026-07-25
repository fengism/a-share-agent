import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SymbolFormats:
    """Purpose: 封装股票代码的多种标准化格式，包括原始代码、交易所前缀和交易所缩写。"""

    raw: str  # "000001"
    prefixed_upper: str  # "SZ000001"
    prefixed_lower: str  # "sz000001"
    exchange: str  # "SZ"


def classify_exchange(code: str) -> str:
    """Classify the exchange of a 6-digit stock code based on its first digit.

    Param:
        code: 6-digit stock code string
    Return:
        exchange code: "SH" for 6/9 prefix, "SZ" for 0/3 prefix, "BJ" for 8 prefix
    """
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
    """Normalize a stock code into all standard formats.

    Param:
        raw: raw stock code, optionally with SH/SZ/BJ prefix
    Return:
        SymbolFormats with raw code, prefixed variants, and detected exchange
    """
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
    """Add sh/sz prefix to a numeric index symbol based on the leading digit.

    Param:
        symbol: index symbol, optionally already prefixed with sh/sz
    Return:
        prefixed index symbol for Sina API
    """
    if symbol.startswith(("sh", "sz")):
        return symbol
    if symbol.startswith("0"):
        return f"sh{symbol}"
    return f"sz{symbol}"


def normalize_index_symbol_v2(symbol: str) -> str:
    """Add sh/sz prefix based on whether the symbol starts with 6 (SH) or not (SZ).

    Param:
        symbol: index symbol, optionally already prefixed with sh/sz
    Return:
        prefixed index symbol for Sina API
    """
    if symbol.startswith(("sh", "sz")):
        return symbol
    if symbol.startswith("6"):
        return f"sh{symbol}"
    return f"sz{symbol}"


def normalize_index_code(symbol: str) -> str:
    """Strip sh/sz prefix from an index symbol, returning the bare numeric code.

    Param:
        symbol: index symbol, optionally prefixed with sh/sz
    Return:
        bare numeric index code without prefix
    """
    if symbol.startswith(("sh", "sz")):
        return symbol[2:]
    return symbol


def normalize_stock_name(name: str) -> str:
    """Strip whitespace from a stock name string.

    Param:
        name: stock name string (may be None)
    Return:
        stripped stock name with spaces removed
    """
    return str(name or "").strip().replace(" ", "")


def contains_stock_reference(text: str, code: str, code_name: str) -> bool:
    """Check whether a text contains a reference to a specific stock by code or name.

    Param:
        text: text to search within
        code: stock code to look for
        code_name: stock name to look for (may include ST/N prefixes)
    Return:
        True if the text contains the code or any name alias
    """
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
