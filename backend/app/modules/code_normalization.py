"""导入表格的股票代码归一，概念库与行业分类导入器共用同一套口径。

统一规则：港股为 5 位数字（如 00700.HK，与 financial_data.hk.service.normalize_hk_code
一致），沪深/北证为 6 位数字；market_group 取 A / HK / OVERSEAS。
"""

from __future__ import annotations

_A_SUFFIXES = {"SZ", "SH", "BJ"}
_HK_EXCHANGE_HINTS = {"港股", "HK", "香港"}
_A_EXCHANGE_HINTS = {"A股", "A", "沪深", "沪市", "深市"}


def _bare_market_and_suffix(base: str) -> tuple[str, str]:
    """按裸代码的数字前缀推断市场；5 位纯数字判为港股（A 股代码均为 6 位）。"""
    if base.startswith(("4", "8", "92")):
        return "A", "BJ"
    if base.startswith(("5", "6", "9")):
        return "A", "SH"
    if base.isdigit() and len(base) == 5:
        return "HK", "HK"
    return "A", "SZ"


def _pad_base(base: str, suffix: str) -> str:
    if not base.isdigit():
        return base
    width = 5 if suffix == "HK" else 6
    if len(base) <= width:
        return base.zfill(width)
    return base


def normalize_imported_stock_code(raw: str, exchange_hint: str = "") -> tuple[str, str, str]:
    """把导入表格里的股票代码归一为 (stock_code, exchange_suffix, market_group)。

    与两个导入器此前的行为保持兼容，差异仅在港股：.HK 代码统一补齐到 5 位；
    无后缀的 5 位纯数字判为港股（此前因先补齐到 6 位导致该分支永不生效，
    会被误判成深市 A 股，如 00700 → 000700.SZ）。
    """
    value = str(raw or "").strip().replace(" ", "")
    if not value:
        return "", "", ""

    if "." in value:
        base, suffix = value.rsplit(".", 1)
        suffix = suffix.upper()
        base = _pad_base(base, suffix)
        market = "A" if suffix in _A_SUFFIXES else ("HK" if suffix == "HK" else "OVERSEAS")
        return f"{base}.{suffix}", suffix, market

    base = value
    hint = exchange_hint.strip().upper()
    if hint in _HK_EXCHANGE_HINTS:
        market, suffix = "HK", "HK"
    elif hint in _A_EXCHANGE_HINTS:
        market = "A"
        if base.startswith(("4", "8", "92")):
            suffix = "BJ"
        elif base.startswith(("5", "6", "9")):
            suffix = "SH"
        else:
            suffix = "SZ"
    else:
        market, suffix = _bare_market_and_suffix(base)
    return f"{_pad_base(base, suffix)}.{suffix}", suffix, market
