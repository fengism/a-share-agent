"""潜力股模块内部共享的小工具。"""

from __future__ import annotations

import pandas as pd


def _normalize_code(value: object) -> str:
    text = str(value or "").strip()
    if text[:2].upper() in {"SH", "SZ", "BJ"}:
        text = text[2:]
    return text.zfill(6) if text.isdigit() else text

def _float_or_none(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None

def _limit_ratio(code: str, board: str | None) -> float:
    if code.startswith(("300", "301", "688")):
        return 0.20
    if code.startswith(("4", "8", "920")):
        return 0.30
    if board and ("创业" in board or "科创" in board):
        return 0.20
    if board and "北" in board:
        return 0.30
    return 0.10
