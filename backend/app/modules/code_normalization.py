"""主数据手工维护与导入共用的证券身份归一规则。"""

from __future__ import annotations

import re

_A_SUFFIXES = {"SZ", "SH", "BJ"}
_EXCHANGE_HINTS = {"港股": "HK", "香港": "HK", "沪市": "SH", "深市": "SZ"}
_A_HINTS = {"A", "A股", "沪深"}


def _a_suffix(base: str) -> str:
    base = base.zfill(6)
    if base.startswith(("4", "8", "92")):
        return "BJ"
    if base.startswith(("5", "6", "9")):
        return "SH"
    return "SZ"


def normalize_stock_identity(
    raw: str, exchange_hint: str = "", market_group: str = "",
) -> tuple[str, str, str]:
    """返回代码、交易所和市场；显式提供的市场/交易所不能与后缀冲突。"""
    value = str(raw or "").strip().upper()
    hint = str(exchange_hint or "").strip().upper()
    hint = _EXCHANGE_HINTS.get(hint, hint)
    market = market_group.strip().upper()
    if hint == "OVERSEAS":
        if market and market != "OVERSEAS":
            raise ValueError("交易所与市场不一致")
        market, hint = "OVERSEAS", ""
    if hint in _A_HINTS:
        if market and market != "A":
            raise ValueError("交易所与市场不一致")
        market, hint = "A", ""
    # Excel 数值单元格有时会带 .0；不能把它识别成海外交易所后缀。
    if re.fullmatch(r"[0-9]+\.0+", value):
        value = value.split(".", 1)[0]
    if not value:
        raise ValueError("股票代码不能为空")

    if "." in value:
        base, suffix = value.rsplit(".", 1)
        if hint and hint != suffix:
            raise ValueError("股票代码后缀与交易所不一致")
    else:
        base = value
        if hint:
            suffix = hint
        elif market == "HK":
            suffix = "HK"
        elif market == "OVERSEAS":
            suffix = ""
        elif market == "A":
            suffix = _a_suffix(base)
        elif base.isdigit() and len(base) == 5:
            suffix = "HK"
        else:
            suffix = _a_suffix(base)

    inferred_market = "A" if suffix in _A_SUFFIXES else ("HK" if suffix == "HK" else "OVERSEAS")
    if market and market != inferred_market:
        raise ValueError("股票代码与市场不一致")
    if inferred_market in {"A", "HK"}:
        width = 5 if inferred_market == "HK" else 6
        if not re.fullmatch(r"[0-9]+", base) or len(base.lstrip("0") or "0") > width:
            raise ValueError("A 股代码须为 6 位数字，港股代码须为 5 位数字")
        base = (base.lstrip("0") or "0").zfill(width)
    elif not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]*", base) or (
        suffix and not re.fullmatch(r"[A-Z][A-Z0-9]*", suffix)
    ):
        raise ValueError("无效的海外股票代码或交易所后缀")
    return f"{base}.{suffix}" if suffix else base, suffix, inferred_market


def normalize_imported_stock_code(raw: str, exchange_hint: str = "") -> tuple[str, str, str]:
    """导入器将非法身份计入无效行；手工维护则直接返回校验错误。"""
    try:
        return normalize_stock_identity(raw, exchange_hint)
    except ValueError:
        return "", "", ""
